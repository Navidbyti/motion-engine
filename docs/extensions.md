# Extension API

Core entry points are registries. Extension identifiers are namespaced, such as `org.example.chart.radial` or `adobe.after_effects`. Each extension publishes a manifest with semantic version, supported OS, runtime, input/output kinds, editability guarantees, and the MotionSpec versions it accepts. M1's `register_parser(".ext", parser)` is the first working extension point; a parser returns evidence records and issues without interpreting them.

```python
class SourceParser:
    def supports(self, media_type: str) -> bool: ...
    def extract(self, artifact, options) -> EvidenceBundle: ...

class Primitive:
    def validate(self, element, context) -> list[Issue]: ...
    def compile(self, element, context) -> LayerPlan: ...

class AssetProvider:
    def request(self, prompt, constraints) -> AssetJob: ...
    def provenance(self, job) -> dict: ...

class OutputAdapter:
    def capabilities(self) -> CapabilityManifest: ...
    def build(self, plan, assets) -> list[Artifact]: ...
    def verify_native(self, artifacts) -> list[Issue]: ...
```

An element's `kind` chooses its primitive. `plugin.id` and `plugin.version` pin custom behavior; `params` are validated by that plugin's own schema. Core does not interpret unknown plugin parameters. The planner compares the primitive's output requirements with every requested adapter before build. It rejects absent features when `policies.unsupportedFeature` is `error`; `warn` requires a named, reviewable fallback and cannot quietly erase content.

### Baseline primitives

`text`, `shape`, `image`, `video`, `audio`, `chart.bar`, `chart.line`, `chart.scatter`, `card`, `counter`, `table`, `disclosure`, and `composition` are candidates for the first registry. Implement only what a milestone requires, but keep IDs, bounds, timing, style, data binding, and keyframes consistent across them. Numeric charts map values to geometry deterministically; generative model pixels cannot be treated as source data.

### Compatibility rule

Breaking changes increment MotionSpec's major version and require a migration. Adapters declare supported spec and app versions. A migration writes a new file and a change report, preserving the original.
