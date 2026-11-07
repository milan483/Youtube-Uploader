# Automatic release builds

Publishing a GitHub release should build its tagged source into Windows and
Linux x86-64 desktop packages and attach both archives to that release.
Pull request and manual runs should produce downloadable Actions artifacts
for verification. Keep release attachment separate from read-only build jobs.
Credentials and runtime state stay outside the build.

## Verification

- Local Linux PyInstaller build and startup check from the extracted archive passed.
- Workflow lint and whitespace checks passed.
- GitHub runner validation is tracked on the draft PR. Attaching files to a
  published release requires the first real release using this workflow.
