"""
L5: ModelGateway placeholder.
Real implementation built in Micro-phase 3 (gateway slice).
StubGateway is used until then — it raises NotImplementedError
so any accidental prod call is immediately visible in logs.
"""

class StubGateway:
    """
    Placeholder gateway. Fulfills the ctx["gateway"].route() contract.
    Raises NotImplementedError if actually called — makes missing 
    implementation impossible to miss in logs/tests.
    Replace with real ModelGateway when L5 is built.
    """
    async def route(self, capability: str, input_data: dict) -> dict:
        raise NotImplementedError(
            f"ModelGateway not yet built. "
            f"Called with capability='{capability}' for gen_id={input_data.get('gen_id')}. "
            f"Build L5 ModelGateway in gateway slice."
        )
