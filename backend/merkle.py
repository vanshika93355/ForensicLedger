"""
merkle.py — Merkle Tree implementation for ForensicLedger
Pure stdlib: hashlib, json only.
"""

import hashlib
import json


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def digest(data: bytes) -> str:
    """Return the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    """Combine two hex digests (in binary pairs) into one parent digest."""
    try:
        combined = bytes.fromhex(left) + bytes.fromhex(right)
    except (ValueError, TypeError):
        combined = (left + right).encode()
    return digest(combined)


# ---------------------------------------------------------------------------
# MerkleTree
# ---------------------------------------------------------------------------

class MerkleTree:
    """
    Binary Merkle tree whose leaves are hex SHA-256 strings.

    Attributes
    ----------
    _leaves : list[str]   – original leaf hashes (bottom layer)
    _tree   : list[list[str]] – layers[0] = leaves … layers[-1] = [root]
    """

    def __init__(self, leaves: list[str]) -> None:
        self._leaves: list[str] = list(leaves)
        self._tree: list[list[str]] = []
        if self._leaves:
            self._build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def root(self) -> str | None:
        """Merkle root hex string, or None for an empty tree."""
        if not self._tree:
            return None
        return self._tree[-1][0]

    def get_proof(self, leaf_hash: str) -> list[dict]:
        """
        Return the Merkle proof for *leaf_hash*.

        Each element is::

            {'sibling': <hex>, 'position': 'left' | 'right'}

        where *position* is the position of the **sibling** relative to the
        current node.  Returns [] if the leaf is not found.
        """
        if not self._tree or leaf_hash not in self._tree[0]:
            return []

        proof: list[dict] = []
        index = self._tree[0].index(leaf_hash)

        for layer in self._tree[:-1]:          # skip the root layer
            sibling_index, position = self._sibling(index, layer)
            proof.append({
                "sibling": layer[sibling_index],
                "position": position,
            })
            index //= 2                        # move up to parent index

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: list[dict], root: str) -> bool:
        """
        Recompute the Merkle root from *leaf_hash* + *proof* and compare
        with *root*.  Returns True iff they match.
        """
        current = leaf_hash
        for step in proof:
            sibling = step["sibling"]
            position = step["position"]
            if position == "left":
                current = _hash_pair(sibling, current)
            else:                              # sibling is on the right
                current = _hash_pair(current, sibling)
        return current == root

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Build self._tree as layers from leaves (index 0) up to root (index -1)."""
        self._tree = []
        current_layer = list(self._leaves)
        self._tree.append(current_layer)

        while len(current_layer) > 1:
            next_layer: list[str] = []
            # Duplicate last element when layer length is odd
            padded = current_layer if len(current_layer) % 2 == 0 else current_layer + [current_layer[-1]]
            for i in range(0, len(padded), 2):
                next_layer.append(_hash_pair(padded[i], padded[i + 1]))
            self._tree.append(next_layer)
            current_layer = next_layer

    @staticmethod
    def _sibling(index: int, layer: list[str]) -> tuple[int, str]:
        """
        Return (sibling_index, sibling_position) for *index* within *layer*.

        *sibling_position* is the position of the sibling relative to the
        current node ('left' or 'right').
        """
        if index % 2 == 0:                    # current node is left child
            sibling_index = index + 1
            if sibling_index >= len(layer):    # odd layer: sibling = self
                sibling_index = index
            return sibling_index, "right"
        else:                                  # current node is right child
            return index - 1, "left"


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

def compute_merkle_root(leaves: list[str]) -> str | None:
    """
    Compute and return the Merkle root for *leaves* (hex SHA-256 strings).

    Backward-compatible replacement for the legacy ``merkle_root`` function
    previously inlined in app.py.  Returns None for an empty list.
    """
    return MerkleTree(leaves).root


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    PASS = "\033[32mPASS\033[0m"
    FAIL = "\033[31mFAIL\033[0m"
    failures = 0

    def check(label: str, condition: bool) -> None:
        global failures
        status = PASS if condition else FAIL
        if not condition:
            failures += 1
        print(f"  [{status}] {label}")

    # --- build tree with 5 leaves ---
    raw_data = [b"block0", b"block1", b"block2", b"block3", b"block4"]
    leaves   = [digest(d) for d in raw_data]

    tree = MerkleTree(leaves)
    root = tree.root

    print("=== MerkleTree self-test (5 leaves) ===")
    print(f"  Root: {root}\n")

    # 1. Root is a 64-char hex string
    check("root is 64-char hex", root is not None and len(root) == 64)

    # 2. compute_merkle_root matches
    check("compute_merkle_root matches", compute_merkle_root(leaves) == root)

    # 3. Proof + verification for every leaf
    all_verified = True
    for i, lh in enumerate(leaves):
        proof = tree.get_proof(lh)
        ok    = MerkleTree.verify_proof(lh, proof, root)
        if not ok:
            all_verified = False
    check("verify_proof succeeds for all 5 leaves", all_verified)

    # 4. Wrong leaf → verify_proof returns False
    fake_leaf = digest(b"evil_block")
    fake_proof = tree.get_proof(leaves[0])        # proof for leaf[0]
    check("verify_proof rejects wrong leaf", not MerkleTree.verify_proof(fake_leaf, fake_proof, root))

    # 5. Unknown leaf → get_proof returns []
    check("get_proof returns [] for unknown leaf", tree.get_proof(fake_leaf) == [])

    # 6. Empty tree
    empty_tree = MerkleTree([])
    check("empty tree root is None", empty_tree.root is None)

    # 7. Single-leaf tree: the while-loop exits immediately (only 1 node),
    #    so the root equals the leaf itself.
    single = MerkleTree([leaves[0]])
    check("single-leaf root equals the leaf itself", single.root == leaves[0])

    # 8. digest() produces expected sha256
    expected = hashlib.sha256(b"hello").hexdigest()
    check("digest() matches hashlib.sha256", digest(b"hello") == expected)

    print()
    if failures == 0:
        print(f"All tests {PASS}")
    else:
        print(f"{failures} test(s) {FAIL}")
        sys.exit(1)
