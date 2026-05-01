import subprocess
from fastapi.templating import Jinja2Templates

_git_rev = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"],
    capture_output=True, text=True,
).stdout.strip() or "dev"

templates = Jinja2Templates(directory="templates")
templates.env.globals["cache_bust"] = _git_rev
