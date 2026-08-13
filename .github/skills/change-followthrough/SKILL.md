---
name: change-followthrough
description: 'Update follow-up project artifacts after code changes. Use when a change should also update CHANGELOG.md, README.md, CLI examples, API/MCP docs, and targeted tests. Good for release hygiene, documentation sync, example refresh, and post-change validation.'
argument-hint: 'Describe the code changes and affected commands, APIs, or user-facing behavior'
user-invocable: true
---

# Change Followthrough

## What This Skill Does

Keeps repository-facing artifacts aligned after code changes. Use it when implementation changes affect user-visible behavior, command syntax, output, examples, docs, or test expectations.

This skill is for the followthrough work after code edits:
- Update changelog entries
- Refresh README examples and command snippets
- Sync API, MCP, or feature-specific documentation
- Adjust or add tests for changed behavior
- Run the relevant test subset and report what was validated

## When to Use

Use this skill when the request involves any of the following:
- A CLI flag, command signature, output, or example changed
- API wrapper behavior changed and docs/examples may now be stale
- MCP tool arguments or behavior changed
- A bug fix should be reflected in changelog and user docs
- Tests should be updated to match corrected behavior
- The user asks to "update the changelog", "refresh the README", "fix docs/examples", or "run tests"

Do not use this skill for code-only refactors with no user-visible behavior change.

## Inputs To Gather

Before editing, identify:
1. Which files changed in the implementation
2. Whether behavior changed for users, CLI consumers, API consumers, or MCP consumers
3. Which examples or docs mention the changed command, option, payload, or response
4. Which tests cover the changed path
5. Whether the repo already has a staged unreleased-version changelog convention that must be preserved
6. The currently released version from `pyproject.toml` and the next unreleased version section already in `CHANGELOG.md`

## Procedure

### 1. Inspect The Change Surface

Start from the changed implementation and map outward:
- Read the modified command, API client, handler, or wrapper code
- Search for related examples in `README.md`, command help text, feature docs, MCP docs, and tests
- Look for generated metadata artifacts only after updating source docs; prefer editing source-of-truth files first

### 2. Decide Which Docs Must Change

Apply these branching rules:
- If CLI syntax or flags changed: update command help examples, README command synopsis, and usage examples
- If output semantics changed: update examples and explanatory text to match actual output
- If an endpoint or wrapper behavior changed: update API/MCP docs and examples that depend on that behavior
- If a fix changes how users troubleshoot or follow up: document the correct next command or workflow
- If no user-visible behavior changed: do not force README/changelog edits unless the user requested them

### 3. Update The Changelog

Follow the repository's existing changelog style exactly.
- In this repository, `pyproject.toml` reflects the latest released version
- Pending changes belong under the next unreleased version section in `CHANGELOG.md` (for example, if `pyproject.toml` is `0.2.1`, ongoing work belongs under `0.2.2 — Unreleased`)
- Reuse the existing unreleased version header if it already exists; do not invent a generic `Unreleased` heading for this repo
- Create or roll the unreleased version header forward only when the release process changes it or the user explicitly asks for a version bump
- Keep entries specific and user-facing
- Record the behavior change, not just the file edit
- Group related fixes together instead of listing every file

Good changelog bullets describe outcomes such as:
- corrected CLI example usage
- clarified response behavior
- fixed MCP flag forwarding
- updated docs to show the correct follow-up workflow

### 4. Update README And Examples

Focus on source-of-truth docs first:
- `README.md`
- command callback/help text
- feature-specific docs under `src/.../*.md`
- MCP documentation if AI tools expose the changed path

For each example:
- Ensure flags and arguments are valid
- Ensure object names and command names match reality
- Ensure examples include required context such as target devices, tags, or variables
- Remove examples that imply unsupported behavior
- If the command does not return IDs or detailed results, show the correct follow-up command to retrieve them

### 5. Update Tests

Update or add tests when behavior, flags, or user-facing expectations changed.

Typical cases:
- CLI flag rename or removal: update argument assertions and help examples
- Wrapper translation change: update command-construction tests
- Output text change: update output assertions only if the wording is part of the user contract

Prefer the smallest relevant test subset first. Examples:
- command-specific integration tests
- wrapper or MCP tests
- unit tests for parsing/translation logic

### 6. Run Validation

Run the narrowest useful validation that proves the change:
- Start with the tests that directly cover the changed feature
- If import path issues exist, run tests against the local source tree when appropriate
- If docs changed but code did not, validate command help or examples where feasible

Report clearly:
- what was run
- whether it passed
- any environment-specific caveats
- anything not run

## Completion Checklist

The task is complete only when all relevant items are true:
- Changed behavior is reflected in the most visible docs
- CLI/API/MCP examples no longer show stale flags or unsupported flows
- Changelog entry exists when requested or warranted by repo convention
- Relevant tests were updated if expectations changed
- Relevant tests were run, or the reason they were not run is stated
- Final summary explains the user-visible outcome, not just file edits

## Quality Bar

Prefer minimal, targeted edits.
Do not update unrelated docs just because they mention nearby features.
Do not edit generated artifacts unless they are intentionally tracked and need to stay in sync with source docs.
Preserve existing terminology and formatting conventions.

## Ambiguities To Resolve When Needed

Ask the user only if the policy is unclear, for example:
- What is the next unreleased version if `pyproject.toml` and `CHANGELOG.md` appear out of sync?
- Should package version metadata also be bumped when the changelog changes?
- Should generated metadata files be edited directly, or regenerated through packaging?

## Example Prompts

- `/change-followthrough Update the changelog, README examples, and tests after changing a CLI flag`
- `/change-followthrough We fixed an MCP wrapper bug; sync docs and run the relevant tests`
- `/change-followthrough Refresh examples and validation after an API behavior change`
