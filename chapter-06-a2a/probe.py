"""A tiny raw A2A client, to see the protocol underneath ADK."""
import asyncio

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest

RETURNS_URL = "http://localhost:8080"


async def main() -> None:
    async with httpx.AsyncClient() as http:
        # 1. Discovery: fetch the Agent Card from the well-known path.
        resolver = A2ACardResolver(httpx_client=http, base_url=RETURNS_URL)
        card = await resolver.get_agent_card()
        print("Talking to:", card.name)

        # 2. Build a client from the card and send one message.
        client = await create_client(
            agent=card, client_config=ClientConfig(streaming=False))
        msg = new_text_message(
            "What is the status of order o1001?", role=Role.ROLE_USER)
        request = SendMessageRequest(message=msg)

        # 3. The response is a Task (or a Message). Print each chunk.
        async for chunk in client.send_message(request):
            print(chunk)


if __name__ == "__main__":
    asyncio.run(main())
