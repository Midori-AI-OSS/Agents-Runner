# Task: Fix pyright errors in agents_runner/ui/pages/artifacts_tab.py

## File
File: `agents_runner/ui/pages/artifacts_tab.py`
Lines: 523, 540, 542

## Category
`artifacts-tab-list-invariance`

## Errors
```
  Line 523: Cannot assign to attribute "_artifacts" for class "ArtifactsTab*"
            "list[ArtifactMeta]" is not assignable to "list[ArtifactMeta | StagingArtifactMeta]"
            Type parameter "_T@list" is invariant
  Line 540: Cannot assign to attribute "_artifacts" for class "ArtifactsTab*"
            "list[StagingArtifactMeta]" is not assignable to "list[ArtifactMeta | StagingArtifactMeta]"
  Line 542: Cannot assign to attribute "_artifacts" for class "ArtifactsTab*"
            "list[ArtifactMeta]" is not assignable to "list[ArtifactMeta | StagingArtifactMeta]"
```

## Fix
The `_artifacts` attribute is typed as `list[ArtifactMeta | StagingArtifactMeta]` but individual assignments use narrower types. Since `list` is invariant, you cannot assign `list[ArtifactMeta]` where `list[ArtifactMeta | StagingArtifactMeta]` is expected.

Fix approaches:
1. Change the assignments to explicitly create correctly-typed lists:
   ```python
   self._artifacts: list[ArtifactMeta | StagingArtifactMeta] = list(artifact_list)
   ```
2. Or change the attribute type to Union:
   ```python
   _artifacts: list[ArtifactMeta] | list[StagingArtifactMeta] | list[ArtifactMeta | StagingArtifactMeta]
   ```
3. Or use `Sequence` from `collections.abc` for the type annotation (covariant):
   ```python
   from collections.abc import Sequence
   _artifacts: Sequence[ArtifactMeta | StagingArtifactMeta]
   ```

## Verification
```bash
uv run pyright agents_runner/ui/pages/artifacts_tab.py
```
