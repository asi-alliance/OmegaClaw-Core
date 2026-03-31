import os
import sys

LICENSE_TEXT = """\
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

def require_license_acceptance():
    print(LICENSE_TEXT)
    while True:
        reply = input("Type 'accept' to continue or 'q' to exit: ").strip().lower()
        if reply == "accept":
            return
        if reply == "q":
            sys.exit(0)
        print("You must type 'accept' or 'q'.", file=sys.stderr)

def config_run_mettaclaw():
    profile = "default"

    print(" ")
    print("Welcome to MeTTaclaw IRC!")
    print(" ")
    require_license_acceptance()

    while True:
        print("Please enter your unique IRC channel. Example: ##MyMeTTa54323")
        channel = input("Enter IRC channel or 'q' to exit: ").strip()
        wait_response = input("Please navigate to https://webchat.quakenet.org/ and enter your name and IRC channel to use Mettaclaw")
        
        if not channel:
            print("IRC channel is required.", file=sys.stderr)
            continue

        if channel.lower() == "q":
            sys.exit(0)

        print("Please navigate to https://webchat.quakenet.org/ and enter your name and IRC channel to use Mettaclaw")
        os.execvp("sh", ["sh", "run.sh", "run.metta", profile, channel])

if __name__ == "__main__":
    config_run_mettaclaw()
