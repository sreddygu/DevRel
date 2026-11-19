# AURA On-Device Action Validation

Validate AURA action-policy behavior before authorizing any physical or remote
action. Model output is a proposal until the action path accepts it.

1. Run `pytest -q tests/test_action.py tests/test_robot.py tests/test_agent.py`
   from `AURA` and record the exact revision and results.
2. Confirm the target, action class, speed/duration limits, emergency-stop
   state, and required approval boundary.
3. Use a fixture, mock, or dry-run path first. Record accepted, rejected, and
   safety-limited requests separately.
4. Obtain explicit approval before connecting to an actuator, robot, IoT device,
   or remote action endpoint.
5. Record target, requested action, policy decision, safety limit, observed
   outcome, and recovery state. Stop on an emergency-stop or policy failure.

This skill never bypasses action policy, emergency stop, safety limits, or user
approval, and never treats a language-model response as an executable command.
