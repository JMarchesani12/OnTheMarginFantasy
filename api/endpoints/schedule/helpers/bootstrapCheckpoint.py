"""Durable local checkpoints for date-by-date season ingestion."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import date


def fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def default_checkpoint_path(database, season_id):
    # Credentials are never persisted. Isolate checkpoints by database and season.
    database_key = fingerprint(str(database))[:24]
    return Path(__file__).resolve().parents[3] / '.cache' / 'season-bootstrap' / f'{database_key}-{season_id}.json'


class BootstrapCheckpoint:
    def __init__(self, path, identity, reset=False):
        self.path = Path(path).expanduser()
        self.identity = identity
        self.completed = set()
        self.complete = False
        self.resuming = False
        if reset or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict) or data.get('version') != 1:
                raise ValueError('invalid format')
            dates = data['completedDates']
            if not isinstance(dates, list) or not all(isinstance(d, str) for d in dates):
                raise ValueError('invalid completed dates')
            parsed = {date.fromisoformat(d) for d in dates}
            if not isinstance(data['complete'], bool) or not isinstance(data['identity'], str):
                raise ValueError('invalid state')
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f'Invalid bootstrap checkpoint {self.path}; use --force to restart') from exc
        if data['identity'] != identity:
            print('[bootstrap] Season configuration changed; restarting date ingestion')
            return
        self.completed = parsed
        self.complete = data['complete']
        self.resuming = True

    def save(self):
        """Atomic replacement preserves the prior checkpoint if writing fails."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path.parent, delete=False) as handle:
                temporary_path = Path(handle.name)
                json.dump(dict(version=1, identity=self.identity, complete=self.complete,
                               completedDates=sorted(d.isoformat() for d in self.completed)), handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
