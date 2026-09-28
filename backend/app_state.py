"""
Bridge Flow - Shared Application State

A small, explicit place to hold the singletons that both the
background asyncio tasks (discovery, TCP server) and the FastAPI
routes need to reach - avoids circular imports between main.py and
the api/ routers.
"""

from discovery.discovery_service import DiscoveryService

discovery_service = DiscoveryService()
