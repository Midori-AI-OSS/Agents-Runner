# Environments Split

- `agents_runner/environments/` is a package that centralizes environment model + parsing + persistence helpers.
- `agents_runner/environments/__init__.py` re-exports the stable import surface used by the GUI.
- No behavior change intended; refactor focuses on keeping modules small and cohesive.

## Prompt Externalization

User-defined environment prompts are stored as external markdown files instead of inline in the JSON state file.

### Storage Structure

- **Prompt files location**: `~/.midoriai/agents-runner/prompts/`
- **Filename format**: `{uuid}.md` (e.g., `abc123-def456-789.md`)
- **State file reference**: JSON contains `prompt_path` field pointing to the markdown file

### Implementation Details

#### Model (`agents_runner/environments/model.py`)

- `PromptConfig` dataclass includes `prompt_path: str` field
- Field stores the full path to the external markdown file

#### Prompt Storage (`agents_runner/environments/prompt_storage.py`)

Helper functions for managing prompt files:

- `user_prompts_dir()` - Returns `~/.midoriai/agents-runner/prompts`
- `ensure_user_prompts_dir()` - Creates the directory if needed
- `generate_prompt_filename()` - Generates UUID-based filename
- `save_prompt_to_file(text, filename)` - Saves prompt text to file
- `load_prompt_from_file(path)` - Loads prompt text from file
- `delete_prompt_file(path)` - Deletes a prompt file

#### Serialization (`agents_runner/environments/serialize.py`)

**Serialization** (`serialize_environment`):
- If prompt has text but no `prompt_path`, saves text to file and stores path
- Stores empty `text` field in JSON when `prompt_path` exists (backwards compatibility)
- Stores `prompt_path` in JSON

**Deserialization** (`_environment_from_payload`):
- If `prompt_path` exists, loads text from file
- Falls back to inline `text` if file doesn't exist (graceful degradation)
- **Migration**: If inline `text` exists but no `prompt_path`, automatically saves to file

#### Storage (`agents_runner/environments/storage.py`)

**Environment deletion**:
- Loads environment before deletion to get `prompt_path` references
- Deletes all associated prompt files
- Then removes environment from state

### Migration Path

The implementation provides automatic migration for existing environments:

1. **First load**: When an environment with inline prompts is loaded:
   - Prompts are saved to external files
   - `prompt_path` field is populated
   - Text remains in memory for immediate use

2. **First save**: When the environment is saved:
   - JSON stores `prompt_path` reference
   - `text` field is saved as empty string (backwards compatibility)

3. **Subsequent loads**: 
   - Text is loaded from external file using `prompt_path`
   - Missing files fall back to inline text (if available)

### Backwards Compatibility

- State file includes both `prompt_path` and `text` fields
- Older versions ignore `prompt_path` and use `text`
- Newer versions prefer `prompt_path` but fall back to `text`
- Empty prompts are handled gracefully without creating files

### Error Handling

All file operations include exception handling:

- **Save failures**: Keep inline text, don't crash
- **Load failures**: Fall back to inline text (if available)
- **Delete failures**: Silently continue (best effort cleanup)
- **Missing directory**: Automatically created on first save
