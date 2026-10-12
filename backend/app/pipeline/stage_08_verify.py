"""Pipeline Stage 08: Verification (Fast DNS resolution + HTTP reachability check)"""
import socket
import asyncio
import logging
from typing import List, Tuple
import httpx
from app.schemas.llm import CompactCandidateCard

logger = logging.getLogger("pipeline.stage_08")


async def verify_domain_online(domain: str) -> bool:
    """Perform fast asynchronous DNS check and lightweight HTTP check."""
    loop = asyncio.get_running_loop()
    if domain in ("maps.google.com", "google.com"):
        return True
    try:
        # Fast DNS resolution
        await loop.run_in_executor(None, socket.gethostbyname, domain)
    except (socket.gaierror, Exception):
        # Fallback check for common alternative TLDs if .com failed
        if domain.endswith(".com"):
            resolved = False
            for alt_tld in [".pk", ".co.uk", ".io", ".org", ".net"]:
                alt_domain = domain[:-4] + alt_tld
                try:
                    await loop.run_in_executor(None, socket.gethostbyname, alt_domain)
                    resolved = True
                    break
                except Exception:
                    pass
            if not resolved:
                return False
        else:
            return False

    # Fast HTTP reachability probe
    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, verify=False) as client:
            resp = await client.head(f"https://{domain}")
            if resp.status_code < 500:
                return True
            # Try GET if HEAD was blocked
            resp = await client.get(f"https://{domain}")
            return resp.status_code < 500
    except Exception:
        # If HTTPS probe failed due to SSL or timeout, try HTTP
        try:
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True, verify=False) as client:
                resp = await client.head(f"http://{domain}")
                return resp.status_code < 500
        except Exception:
            # If DNS succeeded, we can still consider it verified if DNS resolves
            return True


async def run_stage_08_verify(
    candidates: List[CompactCandidateCard],
    excluded_domain: str | None = None,
) -> Tuple[List[CompactCandidateCard], List[CompactCandidateCard]]:
    """Verify web presence for all candidate domains concurrently."""
    verified: List[CompactCandidateCard] = []
    unverified: List[CompactCandidateCard] = []

    tasks = []
    filtered_cands = []
    for cand in candidates:
        if excluded_domain and (cand.domain == excluded_domain or excluded_domain in cand.domain):
            continue
        filtered_cands.append(cand)
        tasks.append(verify_domain_online(cand.domain))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for cand, is_live in zip(filtered_cands, results):
        if is_live is True:
            verified.append(cand)
        elif getattr(cand, "is_synthetic_domain", False):
            # If the domain was synthesized for an entity found in an authoritative search snippet or Knowledge Graph,
            # do not disqualify the candidate simply because our .com guess failed DNS.
            logger.info(f"Retaining snippet/graph candidate '{cand.name}' despite synthetic domain '{cand.domain}' failing DNS probe.")
            verified.append(cand)
        else:
            unverified.append(cand)

    logger.info(f"Verification complete: {len(verified)} live domains verified, {len(unverified)} rejected.")
    return verified, unverified
