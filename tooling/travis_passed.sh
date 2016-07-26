#!/bin/sh -e
#
# Travis-CI runs this after tests pass on master.

# Slide the ci tag to the latest test-passing version. Eat output so it doesn't
# spit out the sensitive GH_TOKEN if something goes wrong.
git push -q "https://${GH_TOKEN}@${GH_REF}" master:ci > /dev/null 2>&1

# Bump quay so it builds a new indexer image:
DOCKER_REPO_SHA=$(curl -s https://api.github.com/repos/mozilla-platform-ops/dxr-infra/git/refs/heads/master | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["object"]["sha"]')
curl -H "Content-Type: application/json" -X POST -d "{\"commit\":\"$DOCKER_REPO_SHA\",\"ref\":\"refs/heads/master\",\"default_branch\":\"master\"}" https://%24token:$QUAY_AUTH_TOKEN@quay.io/webhooks/push/trigger/54f23971-f517-4e6c-88b0-d20453c9fefd
