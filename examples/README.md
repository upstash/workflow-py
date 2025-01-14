# Workflow Examples

This directory has example projects for Upstash Workflow with different frameworks.

## How to Run

There are three alternatives:

1. Deploy the app and use the interface to call it
2. Run the app locally and [create a local tunnel with Ngrok](\(https://upstash.com/docs/workflow/howto/local-development\)) so that QStash can call it. Doing this is simplified through the `bootstrap.sh` script.
3. If you have access to [the QStash development server](https://upstash.com/docs/workflow/howto/local-development), run both the development server and the example workflow project locally.

### `bootstrap.sh` Script

First, set the environment variable `QSTASH_TOKEN`.

The `bootstrap.sh` script makes it possible to start an examplew workflow project and create a Ngrok tunnel in one script. To run it, simply choose the framework and the endpoint you would like to choose as default:

```
bash bootstrap.sh <example-framework>
```

Here is an example call:

```
bash bootstrap.sh nextjs-fastapi
```

Here is what the script does in a nutshell:

* create a Ngrok tunnel from `localhost:8000`
* Public URL of the tunnel is inferred from Ngrok logs. This URL is set to the `UPSTASH_WORKFLOW_URL` environment variable.
* `pip install` and framework-specific commands are executed in the example directory

To use the app, simply send a request through the interface or use the `curl` command.

You will be able to see the workflow executing in the console logs. You can also monitor the events in [the QStash tab of Upstash Console](https://console.upstash.com/qstash?tab=workflow).
