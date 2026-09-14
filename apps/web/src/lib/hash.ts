// P2.1 stale-draft conflict detection: shared digest with the server
// (quant/strategy_sdk/schema.py::strategy_code_hash). WebCrypto SHA-256 where
// available; returns undefined otherwise (server then skips the hash check).
export async function sha256Hex(text: string): Promise<string | undefined> {
  try {
    const subtle = globalThis.crypto?.subtle;
    if (!subtle) return undefined;
    const digest = await subtle.digest(
      "SHA-256",
      new TextEncoder().encode(text),
    );
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  } catch {
    return undefined;
  }
}