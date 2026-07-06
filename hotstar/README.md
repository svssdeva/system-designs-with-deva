# Hotstar — System Design

🚧 **Coming with its video.** This folder will hold the same 7-doc breakdown — how a live
streaming platform held tens of millions of concurrent viewers on one cricket ball: video as
static files on a CDN, the API storm around the stream, pre-provisioned concurrency ladders
(they don't trust autoscaling), panic-mode degradation, and a pub/sub tier holding tens of
millions of sockets.

See [`../upi/`](../upi/) for the format.
