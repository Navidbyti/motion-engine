# Private acceptance fixtures

The owner's source PDF, workbook, derived MotionSpec, and brand material are **not** in this public repository. Keep them under `fixtures/private/` locally; that path is gitignored. Do not open a pull request containing them or commit their rendered frames.

The private test uses a multi-page brief and companion workbook supplied by the project owner. The owner's local engineering package includes a reconciled MotionSpec and source hashes. A maintainer can copy those files into a private fixture directory and run the future acceptance command `motion-engine conformance fixtures/private/<case>`. This command is planned for M6, not implemented in M0.

The fixture tests a demanding path: multilingual right-to-left text, source-faithful financial data, 19 timed beats, multiple chart primitives, exact edits, disclosures, and four editable Adobe outputs. It is an end-to-end conformance case, not the architecture's default project or a public sample.
