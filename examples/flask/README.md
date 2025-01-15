# Upstash Workflow Flask Example

This is an example of how to use Upstash Workflow in a Flask project. You can learn more in [Workflow documentation for Flask](https://upstash.com/docs/workflow/quickstarts/flask).

## Development

> [!TIP]
> You can use [the `bootstrap.sh` script](https://github.com/upstash/workflow-py/tree/master/examples) to run this example with a local tunnel.
>
> Simply set the environment variables as explained below and run the following command in the `workflow-py/examples` directory:
>
> ```
> bash bootstrap.sh flask
> ```

1. Install the dependencies

```bash
pip install Flask upstash-workflow
```

2. Get the credentials from the [Upstash Console](https://console.upstash.com/qstash) and add them to the `.env` file.

```bash
QSTASH_TOKEN=
```

3. Open a local tunnel to port of the development server. Check out our [Local Development](https://upstash.com/docs/workflow/howto/local-development) guide to learn how to set up a local tunnel.

```bash
ngrok http 8000
```

Also, set the `UPSTASH_WORKLFOW_URL` environment variable to the public url provided by ngrok.

4. Run the development server

```bash
flask --app main run -p 8000
```

5. Send a `POST` request to the `/sleep` endpoint.

```bash
curl -X POST "http://localhost:8000/sleep" -d '{"text": "hello world!"}'
```
