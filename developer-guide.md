# Resources

We use AWS to host different resources, the main ones being:
- RDS Postgres database: Hosts all investment data sources and various outputs.
- Secrets Manager: Keeps database and stock price API credentials accesible and safe.
- Lambda functions: Get assets ids, update prices, update news, etc. See /tbainvestetl/lambdas and template.yaml.
- Step functions: To orchestrate (and parallelize) lambda function execution. See /statemachines.


# Development process

Local development process uses on git and GitHub, and relies heavily on the Makefile at project level. File .github/workflows/main.yml shows how the Makefile is used during a push to the GitHub repository. All this in an effort for CI/CD.

0. [Once] Clone GitHub repo.
1. [Once] Authenticate into AWS IAM user in terminal.
2. [Once] Install dependenices in your virtual or conda environment
    - make install
3. Update code. Make a branch.
    - git pull
    - git checkout -b [your_branch]
4. Format, lint, and test
    - make format: Standardizes the code format
    - make lint: Checks for any linting errors. These will be validated again in GitHub Actions (you need 10 out of 10 to pass).
    - make test: Runs tests. These have to pass in GitHub Actions. You can also use VSC to run them and importantly, to debug them if necessary.
    - make pre_pr: Runs format, lint, and test.
5. [Optional] Deploy new code from local. These will be ran in GitHub Actions anyways.
    - make sambuild
    - make samdeploy
6. Commit and push. Go through pull request. Change will be accepted if validation is successful in GitHub Actions.
