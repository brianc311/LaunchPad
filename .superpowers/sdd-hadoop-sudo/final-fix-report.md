# Hadoop sudo password — final fix report

## Fixed findings

- Restored `Card` construction compatibility by moving `encrypted_sudo_password` to the end of the dataclass with a default of `""`.
- Registered the sudo password positionally so existing positional-only `register_card` stubs continue to work.
- Restricted sudo normalization and password stdin delivery to the `hadoop_linux` device profile, including Host Power and command-suite paths.
- Limited sudo recognition to the beginning of a shell command/pipeline segment, preventing rewrites of argument text such as `grep sudo`.
- Normalized generated Hadoop sudo commands with `-S -p ''` to suppress sudo prompts in returned output.
- Preserved the remote command failure when Paramiko stdin has already closed, instead of exposing its `OSError`.
- Updated the stale app-version pin to `1.6.133`.

## Regression coverage

- Added non-Hadoop sudo command passthrough coverage.
- Added command-segment sudo detection coverage.
- Added Host Power coverage ensuring non-Hadoop cards ignore a configured sudo password.
- Added Paramiko closed-stdin coverage for both password and key-auth runners.

## Verification

Executed:

```text
python -m pytest tests/test_hadoop_sudo.py tests/test_hadoop_sudo_wire.py tests/test_capacity_export_filter.py tests/test_site_lookup_api.py tests/test_host_power_api.py tests/test_hadoop_presets.py tests/test_system_connectivity_version.py -q
```

Result: `57 passed in 2.19s`.

IDE diagnostics for modified files: no linter errors.
