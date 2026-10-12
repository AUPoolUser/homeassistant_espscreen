"""Run the firmware's render test through its encrypted API; no HA actions."""
import argparse
import asyncio
import re
from pathlib import Path
import yaml
from aioesphomeapi import APIClient, LogLevel

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='cyd-2432s028.local')
    parser.add_argument('--name', default='cyd-2432s028', help='Expected DEVICE_NAME')
    parser.add_argument('--secrets', type=Path, default=Path(__file__).resolve().parents[1] / 'secrets.yaml')
    args = parser.parse_args()
    secrets = yaml.safe_load(args.secrets.read_text())
    client = APIClient(args.host, 6053, noise_psk=secrets['api_encryption_key'], client_info='CYD UI diagnostics', expected_name=args.name)
    await client.connect(login=True)
    try:
        info = await client.device_info()
        print(f'Connected: {info.name}, ESPHome {info.esphome_version}, compiled {info.compilation_time}', flush=True)
        _, services = await client.list_entities_services()
        test = next(s for s in services if s.name == 'ui_self_test')
        done = asyncio.Event()
        failures = []
        passes = []
        frames = []
        boundaries = []
        def log(msg):
            text = msg.message.decode(errors='replace') if isinstance(msg.message, bytes) else msg.message
            if any(tag in text for tag in ('ui_test', 'UI_TEST', '[health', 'took a long')):
                print(text, flush=True)
            if 'page2=PASS' in text or 'page_check=PASS' in text:
                passes.append(text)
                match = re.search(r'frames=(\d+)', text)
                if match: frames.append(int(match[1]))
            if 'UI_TEST START' in text or 'UI_TEST COMPLETE' in text:
                match = re.search(r'frames=(\d+)', text)
                if match: boundaries.append(int(match[1]))
            if 'FAIL' in text: failures.append(text)
            if 'UI_TEST COMPLETE' in text: done.set()
        client.subscribe_logs(log, log_level=LogLevel.LOG_LEVEL_DEBUG, dump_config=False)
        await client.execute_service(test, {})
        await asyncio.wait_for(done.wait(), timeout=45)
        assert len(passes) == 10, f'Expected 10 page checks, got {len(passes)}'
        assert not failures, failures
        assert len(frames) == 10 and all(b > a for a, b in zip(frames, frames[1:])), f'Render callbacks stalled: {frames}'
        # Ten intermediate observations span only nine cycles. New firmware
        # reports the actual endpoints so the forty-frame check covers all ten,
        # including the final overlay. A burst cannot conceal a stalled cycle.
        assert len(boundaries) == 2, 'Update the test firmware to report complete frame boundaries'
        assert boundaries[1] - boundaries[0] >= 40, f'Too few rendered frames: {boundaries}'
        print('PASS: 10 page checks and 50 overlay render cycles completed', flush=True)
    finally:
        await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
