import asyncio
import os
import sys
import json
from pathlib import Path

# Add backend directory to sys.path to resolve imports correctly
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from google.adk.tools.skill_toolset import SkillToolset
from google.adk.skills import load_skill_from_dir
from app.config import settings
from app.agents.schemas import WorkflowInput
from app.agents.mcp_tools import create_mcp_toolset
from app.agents.intake_agent import build_intake_agent
from app.agents.safety_guidance_agent import build_safety_guidance_agent
from app.agents.plan_generator_agent import build_plan_generator_agent
from app.agents.plan_reviewer_agent import build_plan_reviewer_agent, SKILL_DIR
from app.agents.workflow import run_fitpath_workflow


async def main():
    print("==================================================")
    print(" FitPath Live Agent Workflow Demo")
    print("==================================================")

    # 1. Check for Live Gemini Key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("\n[ERROR] GOOGLE_API_KEY environment variable is missing.")
        print("This demo requires a live Gemini API key to run a real end-to-end workflow.")
        print("Please configure your .env file or export the key, then run again.")
        print("Exiting.\n")
        sys.exit(1)
    
    print(f"[OK] Detected GOOGLE_API_KEY")
    print(f"[OK] Using Model: {settings.MODEL_NAME}")
    print("[OK] Running in LIVE Gemini mode\n")

    # 2. Initialize Dependencies
    print("Initializing ADK toolsets...")
    
    mcp_toolset = create_mcp_toolset()
    discovered_tools = await mcp_toolset.get_tools()
    print(f"[OK] MCP Toolset running. Discovered tools: {[t.name for t in discovered_tools]}")

    print(f"Loading reviewer skill from: {SKILL_DIR}")
    try:
        skill = load_skill_from_dir(SKILL_DIR)
        skill_toolset = SkillToolset(skills=[skill])
        print("[OK] Skill loaded successfully")
    except Exception as e:
        print(f"\n[ERROR] Failed to load skill: {e}")
        await mcp_toolset.close()
        sys.exit(1)

    # 3. Build Agents
    print("Building agents...")
    intake = build_intake_agent()
    safety = build_safety_guidance_agent()
    generator = build_plan_generator_agent(mcp_toolset)
    reviewer = build_plan_reviewer_agent(skill_toolset)

    # 4. Prepare Input
    workflow_input = WorkflowInput(
        goal="Improve stamina and flexibility",
        fitness_level="beginner",
        duration_days=30,
        available_time_mins=30,
        days_per_week=3,
        equipment=["No equipment"],
        preferred_days=["Monday", "Wednesday", "Friday"],
        safety_status="safe",
        safety_message=""
    )

    print("\n--- Input Profile ---")
    print(json.dumps(workflow_input.model_dump(), indent=2))

    print("\nStarting live workflow... (This will take a minute or two)\n")

    try:
        # Run workflow
        result = await run_fitpath_workflow(
            workflow_input=workflow_input,
            mcp_toolset=mcp_toolset,
            intake_agent=intake,
            safety_guidance_agent=safety,
            plan_generator_agent=generator,
            plan_reviewer_agent=reviewer,
        )

        print("==================================================")
        print(" Workflow Complete!")
        print("==================================================")
        
        print(f"\nFinal Status: {result.workflow_status}")

        if result.fitness_plan:
            print("\n--- Final Plan Data ---")
            print(f"Goal: {result.fitness_plan.roadmap.progression_notes}")
            print(f"Total Weeks: {result.fitness_plan.roadmap.total_weeks}")
            print("\nWeek 1 Preview:")
            for day in result.fitness_plan.week_1.days:
                status = "Rest" if day.is_rest else f"{len(day.exercises)} exercises"
                print(f"  - {day.day}: {day.focus} ({status})")
                if not day.is_rest:
                    for ex in day.exercises:
                        print(f"      * {ex.name} ({ex.sets}x{ex.reps}, {ex.duration_mins}m)")

        print("\n--- Trace Log Summary ---")
        
        mcp_calls = set()
        skill_loaded = False
        
        for idx, event in enumerate(result.trace_events):
            print(f"  {idx+1}. [{event['workflow_stage']}] {event['agent_name']} - {event.get('outcome', 'unknown')} ({event.get('duration_ms', 0)}ms)")
            
            # Identify MCP tool calls
            if "mcp" in event['agent_name'].lower():
                mcp_calls.add(event['agent_name'])
                
            # Identify skill loading
            if event['agent_name'] == "plan_reviewer_agent" and "skill" in event.get("details", "").lower():
                skill_loaded = True
                
        print("\n--- Validation ---")
        if mcp_calls:
            print(f"[OK] MCP Tools Called: {list(mcp_calls)}")
        else:
            print("[WARNING] No explicit MCP tool trace events found (they may be tracked under the generator agent)")
            
        # Check actual tool usage in the generator trace if we recorded it
        generator_traces = [e for e in result.trace_events if e['agent_name'] == 'plan_generator_agent']
        if generator_traces:
            print("[OK] Plan Generator executed")

        reviewer_traces = [e for e in result.trace_events if e['agent_name'] == 'plan_reviewer_agent']
        if reviewer_traces:
            print("[OK] Plan Reviewer executed (Skill skillset attached via app/main.py configuration)")
            
        final_validations = [e for e in result.trace_events if e['agent_name'] == 'final_validator_node']
        if final_validations:
            print("[OK] Final Validator node executed successfully")

    except Exception as e:
        print(f"\n[ERROR] Workflow failed: {e}")
    finally:
        print("\nCleaning up...")
        await mcp_toolset.close()
        await skill_toolset.close()

if __name__ == "__main__":
    asyncio.run(main())
