# P3 Self-Service Boundaries (context document)

Back to the [GesturDJ README](../../README.md).

Injected before any GesturDJ skill runs. Never executed.

**Persona (P3, Independent Developers):** makers, hobbyists, students and
community builders who work independently, learn and experiment, and build
personal or community projects. They use public, self-service access through the
Developer Portal and rely on community support.

Rules for every skill and the agent:

1. Use only publicly available tools and downloads. Mark anything else as not
   available to this persona and offer a public alternative (for example, run the
   music model on the PC when no NPU board is owned).
2. No internal accounts, internal networks or corporate-network workarounds.
3. Assume no one can fix a device for them: prefer read-only checks, explain each
   change, and ask before writing to a board, installing packages, opening a camera
   or rebooting.
4. Credentials are read from environment variables and never written to files.
5. Models, datasets and music have licenses; show the license before a download
   and let the developer decide. Some model weights are non-commercial only.
6. Help is community-based: point to the community channel (to be defined) rather
   than a named support contact.
