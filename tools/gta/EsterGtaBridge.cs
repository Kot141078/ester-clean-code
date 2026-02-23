// EsterGtaBridge.cs
// ScriptHookVDotNet script for GTA V single-player telemetry push.
//
// Prerequisites:
// - ScriptHookV
// - ScriptHookVDotNet (v3+)
// Place this file into: <GTA>\scripts\
// It will POST telemetry to: http://127.0.0.1:8090/gta/ingest

using GTA;
using GTA.Math;
using System;
using System.Globalization;
using System.Net.Http;
using System.Text;

public class EsterGtaBridge : Script
{
    private static readonly HttpClient Http = new HttpClient();
    private DateTime _nextPushUtc = DateTime.MinValue;
    private readonly int _periodMs = 900;
    private readonly string _endpoint = "http://127.0.0.1:8090/gta/ingest";

    public EsterGtaBridge()
    {
        Tick += OnTick;
        Interval = 200;
        Http.Timeout = TimeSpan.FromMilliseconds(1200);
    }

    private static string Num(float v)
    {
        return v.ToString("0.###", CultureInfo.InvariantCulture);
    }

    private static string Esc(string s)
    {
        if (s == null) return "";
        return s.Replace("\\", "\\\\").Replace("\"", "\\\"");
    }

    private static string BuildPayload(Ped p, bool inVehicle, string vehicleName, float speedKmh, string zone)
    {
        Vector3 pos = p.Position;
        int wanted = Game.Player.WantedLevel;
        int hp = p.Health;
        int armor = p.Armor;

        return "{"
            + "\"source\":\"gta5_shvdn\","
            + "\"ask\":false,"
            + "\"state\":{"
            + "\"ts_ms\":" + DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + ","
            + "\"wanted\":" + wanted + ","
            + "\"hp\":" + hp + ","
            + "\"armor\":" + armor + ","
            + "\"in_vehicle\":" + (inVehicle ? "true" : "false") + ","
            + "\"vehicle\":\"" + Esc(vehicleName) + "\","
            + "\"speed_kmh\":" + Num(speedKmh) + ","
            + "\"zone\":\"" + Esc(zone) + "\","
            + "\"x\":" + Num(pos.X) + ","
            + "\"y\":" + Num(pos.Y) + ","
            + "\"z\":" + Num(pos.Z)
            + "}"
            + "}";
    }

    private async void OnTick(object sender, EventArgs e)
    {
        if (DateTime.UtcNow < _nextPushUtc) return;
        _nextPushUtc = DateTime.UtcNow.AddMilliseconds(_periodMs);

        try
        {
            Ped p = Game.Player.Character;
            if (p == null || !p.Exists()) return;

            bool inVehicle = p.IsInVehicle();
            Vehicle v = inVehicle ? p.CurrentVehicle : null;
            string vehicleName = (v != null && v.Exists()) ? (v.DisplayName ?? "") : "";
            float speedKmh = (v != null && v.Exists()) ? (v.Speed * 3.6f) : 0f;
            string zone = World.GetZoneNameLabel(p.Position) ?? "";

            string payload = BuildPayload(p, inVehicle, vehicleName, speedKmh, zone);
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            await Http.PostAsync(_endpoint, content).ConfigureAwait(false);
        }
        catch
        {
            // Best effort: never crash game script thread on bridge errors.
        }
    }
}
