[![Try Free](https://img.shields.io/badge/Try%20Free-FalkorDB%20Cloud-FF8101?labelColor=FDE900&link=https://app.falkordb.cloud)](https://app.falkordb.cloud)
[![Dockerhub](https://img.shields.io/docker/pulls/falkordb/falkordb?label=Docker)](https://hub.docker.com/r/falkordb/falkordb/)
[![Discord](https://img.shields.io/discord/1146782921294884966?style=flat-square)](https://discord.com/invite/6M4QwDXn2w)

## Getting Started
[Live Demo](https://code-graph.falkordb.com/)


```bash
flask --app code_graph run --debug
```

Process local git repository, ignoring specific folder(s)

```bash
curl -X POST http://127.0.0.1:5000/process_local_repo -H "Content-Type: application/json" -d '{"repo": "/Users/roilipman/Dev/FalkorDB", "ignore": ["./.github", "./sbin", "./.git","./deps", "./bin", "./build"]}'
```

Process code coverage

```bash
curl -X POST http://127.0.0.1:5000/process_code_coverage -H "Content-Type: application/json" -d '{"lcov": "/Users/roilipman/Dev/code_graph/code_graph/code_coverage/lcov/falkordb.lcov", "repo": "FalkorDB"}'
```

Process git information

```bash
curl -X POST http://127.0.0.1:5000/process_git_history -H "Content-Type: application/json" -d '{"repo": "/Users/roilipman/Dev/falkorDB"}'
```
