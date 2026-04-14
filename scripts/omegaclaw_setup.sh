#!/usr/bin/env bash
set -euo pipefail

########################################################
#  Required parameter is Docker image 
#  Invoke this script:  "./omegaclaw_setup.sh <image>  
#######################################################
image="${1:?usage: $0 <container-image>}"

# Create temporary files
tmp_channel_file="$(mktemp)"
tmp_token_file="$(mktemp)"
tmp_py_file="$(mktemp)"
trap 'rm -f "$tmp_channel_file" "$tmp_token_file" "$tmp_py_file"' EXIT

# Lock down permissions immediately after creation
chmod 0600 "$tmp_channel_file"
chmod 0600 "$tmp_token_file"
chmod 0600 "$tmp_py_file"

cat >"$tmp_py_file" <<'PY'
import sys
import shutil
import textwrap
import getpass

LICENSE_TEXT = """\

** DISCLAIMER **

OmegaClaw is experimental, open-source software developed by SingularityNET Foundation, a Swiss foundation, and distributed and promoted by Superintelligence Alliance Ltd., a Singapore company (collectively, the "Parties"), and is provided "AS IS" and "AS AVAILABLE," without warranty of any kind, express or implied, including but not limited to the implied warranties of merchantability, fitness for a particular purpose, and non-infringement. OmegaClaw is an autonomous AI agent that is designed to independently set goals, make decisions, and take actions (including actions that the user did not specifically request or anticipate) and whose behavior is influenced by large language models provided by third parties, the outputs of which are inherently non-deterministic. Depending on its configuration and the permissions granted to it, OmegaClaw may execute operating-system shell commands, read, write, modify, or delete files, access network resources, send and receive messages through connected communication channels, and modify its own skills, memory, and operational logic at runtime. OmegaClaw may also be susceptible to prompt injection and other adversarial manipulation techniques whereby malicious content embedded in data sources consumed by the agent could influence its behavior in unintended ways. OmegaClaw supports third-party skills and extensions that have not necessarily been reviewed, audited, or endorsed by either of the Parties and that may introduce security vulnerabilities, cause data loss, or result in unintended behavior including data exfiltration. OmegaClaw relies on third-party services, including large language model providers, whose availability, accuracy, cost, and conduct are outside the control of the Parties and whose use is subject to their respective terms, conditions, and privacy policies. The user is solely responsible for configuring appropriate access controls, sandboxing, and permission boundaries, for monitoring, supervising, and constraining OmegaClaw's actions, for ensuring that no sensitive personal data is exposed to the agent without adequate safeguards, and for all actions taken by OmegaClaw on the user's systems or on the user's behalf, including communications sent and files modified. The user is strongly advised to run OmegaClaw in an isolated environment with the minimum permissions necessary for the intended use case. To the maximum extent permitted by applicable law, in no event shall the Parties, their respective board members, directors, contributors, employees, or affiliates be liable for any direct, indirect, incidental, special, consequential, or exemplary damages (including but not limited to damages for loss of data, loss of profits, business interruption, unauthorized transactions, reputational harm, or any damages arising from the autonomous actions taken by OmegaClaw) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise), even if advised of the possibility of such damages. By downloading, installing, running, or otherwise using OmegaClaw, the user acknowledges that they have read, understood, and agreed to this disclaimer in its entirety. This disclaimer supplements but does not replace the terms of the MIT License under which OmegaClaw is released.


"""

def print_wrapped(text: str) -> None:
    width = max(60, min(shutil.get_terminal_size((100, 24)).columns - 2, 100))
    for paragraph in text.strip().split("\n\n"):
        print(textwrap.fill(paragraph, width=width))
        print()

def require_license_acceptance():
    print_wrapped(LICENSE_TEXT)
    print()
    while True:
        reply = input("I HAVE READ AND UNDERSTOOD THE DISCLAIMER. Type 'accept' to continue or 'q' to exit: ").strip().lower()
        if reply == "accept":
            return
        if reply == "q":
            sys.exit(1)
        print("You must type 'accept' or 'q'.", file=sys.stderr)

def config_run_omegaclaw(channel_output_path, token_output_path):
    print(" ")
    print("Welcome to OmegaClaw IRC!")
    print(" ")
    require_license_acceptance()

    while True:
        print("Please enter your unique IRC channel. Example: ##MyOmega54323")
        channel = input("Enter IRC channel or 'q' to exit: ").strip()

        if channel.lower() == "q":
            sys.exit(1)

        if not channel:
            print("IRC channel is required.", file=sys.stderr)
            continue

        break

    while True:
        token = getpass.getpass("Please paste your LLM token and press ENTER or 'q' to exit: ").strip()

        if token.lower() == "q":
            sys.exit(1)

        if not token:
            print("Error: Invalid token", file=sys.stderr)
            continue

        break

    with open(channel_output_path, "w", encoding="utf-8") as f:
        f.write(channel)

    with open(token_output_path, "w", encoding="utf-8") as f:
        f.write(token)

if __name__ == "__main__":
    config_run_omegaclaw(sys.argv[1], sys.argv[2])
PY

python3 "$tmp_py_file" "$tmp_channel_file" "$tmp_token_file" </dev/tty

channel="$(cat "$tmp_channel_file")"
token="$(cat "$tmp_token_file")"
auth_secret="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"

cat <<EOF
============================================
 QuakeNet / OmegaClaw Instructions
============================================
Please go to https://webchat.quakenet.org/
and enter your name and channel.

Authentication step (required):
  In your channel, send this one-time secret exactly once:
  auth ${auth_secret}
  The first nickname that sends it becomes the only accepted user.
  Messages from all other users will be silently ignored.

Stop OmegaClaw:
  docker stop omegaclaw

Restart OmegaClaw:
  docker start omegaclaw

Examine log file in case of problem:
  docker logs -f omegaclaw

EOF

docker rm -f omegaclaw 2>/dev/null || true

docker run -d -it \
  --name omegaclaw \
  --user 65534:65534 \
  --security-opt no-new-privileges:true \
  --init \
  --tmpfs /tmp:size=64m,mode=1777 \
  --tmpfs /run:size=16m,mode=755 \
  --tmpfs /var/tmp:size=64m,mode=1777 \
  -e ANTHROPIC_API_KEY="$token" \
  -e OMEGACLAW_AUTH_SECRET="$auth_secret" \
  "$image" \
  IRC_channel="$channel"
