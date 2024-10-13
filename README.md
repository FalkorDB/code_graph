Process local git repository, ignoring specific folder(s)

curl -X POST http://127.0.0.1:5000/process_local_repo -H "Content-Type: application/json" -d '{"repo": "/Users/roilipman/Dev/FalkorDB", "ignore": ["./.github", "./sbin", "./.git","./deps", "./bin", "./build"]}'


Process code coverage
curl -X POST http://127.0.0.1:5000/process_code_coverage -H "Content-Type: application/json" -d '{"lcov": "/Users/roilipman/Dev/code_graph/code_graph/code_coverage/lcov/falkordb.lcov", "repo": "FalkorDB"}'

Process git information
curl -X POST http://127.0.0.1:5000/process_git_history -H "Content-Type: application/json" -d '{"repo": "/Users/roilipman/Dev/falkorDB"}'
