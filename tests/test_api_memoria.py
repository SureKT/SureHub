class TestMemoryAPI:
    def test_create_and_list(self, client):
        r = client.post("/api/memory", json={"fact": "le gusta el pádel"})
        assert r.status_code == 201
        assert r.json()["fact"] == "le gusta el pádel"

        r = client.get("/api/memory")
        assert r.status_code == 200
        assert [m["fact"] for m in r.json()] == ["le gusta el pádel"]

    def test_patch(self, client):
        mem_id = client.post("/api/memory", json={"fact": "original"}).json()["id"]
        r = client.patch(f"/api/memory/{mem_id}", json={"fact": "corregido"})
        assert r.status_code == 200
        assert r.json()["fact"] == "corregido"

    def test_patch_missing_404(self, client):
        assert client.patch("/api/memory/999", json={"fact": "x"}).status_code == 404

    def test_delete(self, client):
        mem_id = client.post("/api/memory", json={"fact": "borrable"}).json()["id"]
        assert client.delete(f"/api/memory/{mem_id}").status_code == 204
        assert client.get("/api/memory").json() == []

    def test_delete_missing_404(self, client):
        assert client.delete("/api/memory/999").status_code == 404
