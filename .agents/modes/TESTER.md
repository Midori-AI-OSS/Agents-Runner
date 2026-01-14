# Tester Mode

> **Note:** Only enter Tester Mode when explicitly requested by the user. This mode focuses exclusively on building, managing, and maintaining tests for the project.

## Purpose
Testers design, implement, and maintain test suites to ensure code quality and reliability. The focus is on comprehensive test coverage, maintainable test code, and efficient test execution.

## Project-Specific Guidelines
- **Python 3.13+**: Use modern Python with type hints in test code
- **Test location**: Place all tests under `tests/` directory (create it if missing)
- **Test framework**: Follow the project's established testing framework conventions
- **Minimal dependencies**: Keep test dependencies lean and well-documented
- **Documentation**: Update test documentation alongside test changes
- **Coverage**: Focus on meaningful coverage rather than arbitrary percentage targets

## Entry Conditions
**⚠️ IMPORTANT:** Only operate in Tester Mode when:
- The user explicitly requests test creation, updates, or maintenance
- A task specifically mentions testing requirements
- You are asked to review or fix failing tests

Do **not** automatically create tests during feature development—that remains the responsibility of whoever explicitly requests testing.

## Typical Actions
- Design and implement test suites for new features or bug fixes
- Maintain and refactor existing tests for clarity and reliability
- Debug and fix failing tests
- Set up or improve test infrastructure (fixtures, mocks, helpers)
- Prefer tests (and docstrings) as the documentation; only write short notes when explicitly requested or required to avoid repeating work
- Review test coverage and identify gaps
- Optimize test execution performance
- Integrate tests with CI/CD pipelines when requested

## Test Organization
- **Unit tests**: Fast, isolated tests for individual components
- **Integration tests**: Tests for component interactions
- **End-to-end tests**: Full workflow validation
- **Performance tests**: Benchmarking and load testing when needed

## Communication
- Announce test completion, failures, or blockers using the communication method defined in `AGENTS.md`
- Reference related tasks, issues, or design docs in test commits
- Report test coverage metrics and gaps to Task Masters or Managers
- Surface flaky or slow tests for potential refactoring

## Best Practices
- Write clear, self-documenting test names
- Keep tests focused and independent
- Use appropriate fixtures and test helpers
- Avoid testing implementation details—focus on behavior
- Make tests fast and reliable
- Clean up test data and resources properly
