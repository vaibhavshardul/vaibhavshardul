## Naming Convention

This repo requires branches to follow specific format.
Pull Request name format:

```
change_type(jira_ticket): Description
```

Branch name format:

```
change_type/jira_ticket-description
```

**You won't be able to merge PR or push the branch if it's not in the right format!**

Allowed change_types:

```
feat ✨: A new feature. Correlates with MINOR in SemVer
fix 🐛: A bug fix. Correlates with PATCH in SemVer
chore 🔧: changes that do not relate to a fix or feature and don't modify src or test files (for example updating dependencies)
docs 📝: Documentation only changes
refactor ♻️: A code change that neither fixes a bug nor adds a feature
perf ⚡️: A code change that improves performance
test 🧪: Adding missing or correcting existing tests
ci 🔁: Changes to our CI configuration files and scripts (example scopes: Jenkins)
build 📦: Changes that affect the build system or external dependencies (example scopes: pip, docker, npm)
style 🎨: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
```

**Edit a file, create a new file, and clone from Bitbucket in under 2 minutes**

When you're done, you can delete the content in this README and update the file with details for others getting started with your repository.

*We recommend that you open this README in another tab as you perform the tasks below. You can [watch our video](https://youtu.be/0ocf7u76WSo) for a full demo of all the steps in this tutorial. Open the video in a new tab to avoid leaving Bitbucket.*

---

## Setup Python 3.7 or latest one on local

1. Install **python3** on your local machine
2. Run some testing script
---

## Setup MYSQL database on local

Next, you’ll add a new file to this repository.

1. Install mysql and mysql workbench on your local machine
2. Once setup is done then test with your credentials
3. Import hotel uat db on you local db

---
## Setup spark on local

You’ll start by editing this README file to learn how to edit a file in Bitbucket.

1. Install **Apache Spark** on local instance. (For windows (https://phoenixnap.com/kb/install-spark-on-windows-10) and for linux (https://phoenixnap.com/kb/install-spark-on-ubuntu) and for MAC (https://medium.com/beeranddiapers/installing-apache-spark-on-mac-os-ce416007d79f))
2. Once setup is done then pull this repo in your local.
3. Create the **.env** file in the local repo with this param (1. export PYTHONPATH="${PYTHONPATH}: /Path/  " 2. export ENV_FOR_DYNACONF=development).
4. run the .env file (source .env)
---

## Execution Steps

Use these steps to clone from SourceTree, our client for using the repository command-line free. Cloning allows you to work on your files locally. If you don't yet have SourceTree, [download and install first](https://www.sourcetreeapp.com/). If you prefer to clone from the command line, see [Clone a repository](https://confluence.atlassian.com/x/4whODQ).

1. **Source .env**
2. Run **python3 filename.py**

Now that you're more familiar with your Bitbucket repository, go ahead and add a new file locally. You can [push your change back to Bitbucket with SourceTree](https://confluence.atlassian.com/x/iqyBMg), or you can [add, commit,](https://confluence.atlassian.com/x/8QhODQ) and [push from the command line](https://confluence.atlassian.com/x/NQ0zDQ).

---

