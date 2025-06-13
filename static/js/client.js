document.addEventListener("DOMContentLoaded", async () => {
    try {
        const fp = await FingerprintJS.load()
        const result = await fp.get()
        document.getElementById("fingerprint").value = result.visitorId
        console.log("Fingerprint set:", result.visitorId)

        // Optional IP collection
        const ipRes = await fetch("https://api.ipify.org?format=json")
        const ipData = await ipRes.json()
        document.getElementById("ip").value = ipData.ip
    } catch (err) {
        console.error("Fingerprint/IP error:", err)
    }

    // Temporary manual override if needed
    document.getElementById("discord_id").value = "PLACEHOLDER_ID"
})
