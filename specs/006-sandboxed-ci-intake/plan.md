# Implementation Plan

Add a standard-library intake module that clones a supplied base bundle into a new local sandbox, applies the recorded patch, verifies exact evidence, and invokes the existing review gate with the fixed CI suite. Add a PowerShell transport wrapper that asks Orin to export only a bundle, record, and patch, transfers that archive, validates its member names, and calls intake. Sandboxes live under ignored `.ci-sandboxes/` for IDE inspection. No intake code contains commit or remote-write operations beyond temporary export cleanup.
