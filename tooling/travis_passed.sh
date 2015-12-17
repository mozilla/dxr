#!/bin/sh -e

# Slide the ci tag to the latest test-passing version. Eat output so it doesn't
# spit out the sensitive GH_TOKEN if something goes wrong.
git push -q "https://${GH_TOKEN}@${GH_REF}" master:ci > /dev/null 2>&1

# Bump quay so it builds a new indexer image:
curl -H "Content-Type: application/json" -X POST -d "{\"commit\":\"$TRAVIS_COMMIT\",\"ref\":\"refs/heads/master\",\"default_branch\":\"master\"}" https://%24token:$QUAY_AUTH_TOKEN@quay.io/webhooks/push/trigger/fada413b-bb9f-4358-9303-ce742d77921f
