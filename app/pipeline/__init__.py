"""Orchestration: workflows, queueing, scheduling, subscriptions, batches.

The only layer allowed to compose ingest + knowledge + delivery into a single
run. If two layers need to talk to each other, they talk here.
"""
