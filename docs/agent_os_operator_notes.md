# Agent OS Operator Notes

## How Esther asks for an agent

1. Select a template (yemplate_idyo) from e/debug/garage/templatesyo.
2. Send the purpose (yogoalyo) and name (yonameyo) if necessary.
3. Create via itools/garage_make_agent.pie or ePOST/debug/garage/agents/create_from_template.
4. Check eplan.jsonyo and eREADME_agent.txto in the agent folder.

## How Ovner asks Esther to become an agent

1. Specify the type of task (archive, build a plan, collect an artifact, check).
2. Select the closest template from Pask v1.
3. Pass a human-readable target to yo-goal (or yo-goal to API).
4. Launch euron_onsey in safe mode and check the box/log.

## What to enable for Oracle/Sums and why it is dangerous

- By default, yooracleyo and yokommyo are disabled.
- For the Oracle you need to simultaneously:
  - vklyuchit `enable_oracle`,
  - otkryt oracle window,
  - proyti Volition allow.
- For yokommyo you need to enable yoenable_kommyo and have windows comm enabled.
- Risk: network activities expand the attack surface and may disrupt the offline first profile; therefore an explicit window and reason is required.

