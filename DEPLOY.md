# PythonAnywhere deployment

Create a virtual environment with the same Python version as the web app. From the project directory:

```bash
python3.12 -m venv ~/.virtualenvs/python-workshop
~/.virtualenvs/python-workshop/bin/pip install --no-cache-dir -r requirements.txt
```

Create a manually configured web app. Set its source and working directories to the project directory and its virtualenv to the environment created above.

In the PythonAnywhere WSGI configuration, add the project directory to sys.path and import the application:

```python
import sys
path = '/home/YOUR_USERNAME/python-workshop'
if path not in sys.path:
    sys.path.insert(0, path)
from wsgi import application
```

Enable HTTPS. Set the static URL mapping /static/ to the project's static directory. The wsgi module enables secure session cookies. The application generates a private signing key on first start; the instance directory must stay outside version control and must never be mapped as a static directory.

Reload the web app and test a complete quiz, a lower retry, a second player, image upload, an empty detection, and saved results after reload. Check error logs if loading or inference fails. The weights are included in models/; the running application does not download a model or call a remote inference API.

Runtime records are stored under instance/: workshop.db, session.key and images/. Back this directory up before updating the deployment. Do not upload these files to GitHub.
