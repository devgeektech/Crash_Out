"""
State machine and episode repository for Crash Out Multi-Agent Pipeline.

Global index:  outputs/pipeline_index.json
Per episode:   outputs/<ep_id>_<Title>/episode.json

Empty (no video) non-active episodes are pruned on load/save so they cannot
reappear in the index. No separate deleted-episodes tombstone file is used.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.paths import (
    EPISODES_DIR,
    OUTPUT_DIR,
    build_episode_folder_name,
    episode_dir,
    resolve_episode_folder,
)

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(EPISODES_DIR, exist_ok=True)

INDEX_FILE = os.path.join(OUTPUT_DIR, "pipeline_index.json")
LEGACY_STATE_FILE = os.path.join(OUTPUT_DIR, "pipeline_state.json")
# Legacy tombstone file from an earlier approach — never recreate; delete if found.
LEGACY_DELETED_FILE = os.path.join(OUTPUT_DIR, ".deleted_episodes.json")
EPISODE_STATE_FILENAME = "episode.json"
_VIDEO_EXTS = {".mp4", ".webm"}


def _remove_legacy_deleted_file() -> None:
    if os.path.isfile(LEGACY_DELETED_FILE):
        try:
            os.remove(LEGACY_DELETED_FILE)
        except OSError:
            pass


def _ensure_episode_dir(ep: "Episode") -> str:
    """Create episode folder using canonical paths."""
    folder = ep.output_folder or build_episode_folder_name(ep.id, ep.title)
    ep.output_folder = folder
    path = episode_dir(folder)
    marker = os.path.join(path, ".episode_id")
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write(ep.id)
    return folder


def _episode_folder_path(ep: "Episode") -> str:
    folder = ep.output_folder or build_episode_folder_name(ep.id, ep.title)
    return episode_dir(folder)


def _episode_has_video_files(ep: "Episode") -> bool:
    folder = _episode_folder_path(ep)
    if not os.path.isdir(folder):
        return False
    try:
        for root, _, files in os.walk(folder):
            for name in files:
                if os.path.splitext(name)[1].lower() in _VIDEO_EXTS:
                    return True
    except OSError:
        return False
    return False


def _should_keep_episode(ep: "Episode", active_id: Optional[str]) -> bool:
    """Keep episodes that still matter — never drop mid-pipeline work."""
    if ep.id == active_id:
        return True
    if _episode_has_video_files(ep):
        return True
    # Queue-backed drafts (catalog / manual add) must survive selection switches.
    if getattr(ep, "catalog_id", None):
        return True
    # Manual/catalog flows approve concept before any MP4 exists. Keep them.
    if ep.script:
        return True
    if int(getattr(ep, "current_gateway", 1) or 1) >= 2:
        return True
    status = (getattr(ep, "status", "") or "").upper()
    if status and status not in {"DRAFT", "WAITING_GATEWAY_1"}:
        return True
    return False


class Episode(BaseModel):
    id: str
    user_id: Optional[int] = None
    title: str = "Untitled Episode"
    episode_number: int = 0
    output_folder: Optional[str] = None
    status: str = "DRAFT"
    # Studio production workflow (parallel to HITL gateway status)
    production_status: str = "draft"  # draft|scripting|generating|published
    current_gateway: int = 1
    selected_engine: str = "mock"
    final_platform_decision: Optional[str] = "mock"
    catalog_id: Optional[str] = None
    script_key: str = "hoa_violation"
    cultural_hook: Optional[str] = None

    @property
    def hook(self) -> str:
        if self.cultural_hook:
            return self.cultural_hook
        if self.selected_concept and isinstance(self.selected_concept, dict):
            return str(self.selected_concept.get("cultural_hook") or self.selected_concept.get("hook") or "")
        return ""

    available_concepts: List[Dict[str, Any]] = []
    selected_concept: Optional[Dict[str, Any]] = None

    script: Optional[Dict[str, Any]] = None
    merch_punchline: Optional[str] = None
    script_versions: List[Dict[str, Any]] = []

    video_url: Optional[str] = None
    video_engine_used: Optional[str] = None
    video_render_time_sec: float = 0.0
    video_qa_passed: bool = False
    native_audio_enabled: bool = True

    scene_videos: List[Dict[str, Any]] = []
    merged_video_url: Optional[str] = None
    scenes_merged: bool = False
    merging_in_progress: bool = False
    clip_history: Dict[str, List[Dict[str, Any]]] = {}
    generation_jobs: List[Dict[str, Any]] = []
    cost_ledger: List[Dict[str, Any]] = []

    audio_mix_url: Optional[str] = None
    character_stems: Dict[str, str] = {}
    audio_duration: float = 0.0

    social_posts: Dict[str, Any] = {}
    merch_mockup_url: Optional[str] = None
    merch_listing: Dict[str, Any] = {}

    seeding_drafts: List[Dict[str, Any]] = []
    revision_notes: List[Dict[str, Any]] = []

    # Legacy mix field kept for old episode.json; audio is Vidu-native in-clip
    audio_mix: Dict[str, Any] = {}
    # Dialogue timing rows feed Vidu timeline prompts (not a TTS engine)
    dialogue_timing: List[Dict[str, Any]] = []

    # QA checklists + continuity last-frame paths
    qa_checklists: Dict[str, Any] = {}
    continuity_frames: Dict[str, str] = {}

    qa_logs: List[str] = []
    sla_metrics: Dict[str, float] = {}
    gate_history: List[Dict[str, Any]] = []

    # Last Studio UI position (survives hard refresh when URL is bare /studio)
    studio_ui_stage: Optional[int] = None
    studio_ui_scene: Optional[int] = None

    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


def episode_state_path(ep: Episode) -> str:
    folder = ep.output_folder or build_episode_folder_name(ep.id, ep.title)
    return os.path.join(episode_dir(folder), EPISODE_STATE_FILENAME)


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, path)


def _index_entry(ep: Episode) -> Dict[str, Any]:
    return {
        "id": ep.id,
        "title": ep.title,
        "episode_number": getattr(ep, "episode_number", 0) or 0,
        "output_folder": ep.output_folder,
        "status": ep.status,
        "production_status": getattr(ep, "production_status", "draft") or "draft",
        "current_gateway": ep.current_gateway,
        "catalog_id": ep.catalog_id,
        "script_key": ep.script_key,
        "updated_at": ep.updated_at,
        "scenes_merged": ep.scenes_merged,
        "has_video": _episode_has_video_files(ep),
    }


class StateManager:
    def __init__(self):
        self.episodes: Dict[str, Episode] = {}
        self.active_episode_id: Optional[str] = None
        self._load()

    def _load(self) -> None:
        _remove_legacy_deleted_file()

        if os.path.exists(LEGACY_STATE_FILE):
            try:
                self._migrate_legacy_monolith()
            except Exception as exc:
                print(f"Error migrating pipeline_state.json: {exc}")

        if os.path.exists(INDEX_FILE):
            try:
                with open(INDEX_FILE, "r", encoding="utf-8") as fh:
                    index = json.load(fh)
                self.active_episode_id = index.get("active_episode_id")
                for ep_id, meta in (index.get("episodes") or {}).items():
                    folder = (meta or {}).get("output_folder") or build_episode_folder_name(
                        ep_id, (meta or {}).get("title") or ep_id
                    )
                    path = os.path.join(episode_dir(folder), EPISODE_STATE_FILENAME)
                    ep = self._read_episode_file(path)
                    if ep is None:
                        continue
                    if not ep.output_folder:
                        ep.output_folder = folder
                    self.episodes[ep.id] = ep
            except Exception as exc:
                print(f"Error loading pipeline_index.json: {exc}")

        self._discover_orphan_episodes()
        self._prune_empty_episodes(persist=True)

        if self.active_episode_id not in self.episodes and self.episodes:
            self.active_episode_id = self._preferred_active_id()
            self._write_index()

    def _preferred_active_id(self) -> Optional[str]:
        for ep in self.episodes.values():
            folder = _episode_folder_path(ep)
            if os.path.isfile(os.path.join(folder, "merged_60s.mp4")) or os.path.isfile(os.path.join(folder, "video", "merged_60s.mp4")):
                return ep.id
        return next(iter(self.episodes), None)

    def _read_episode_file(self, path: str) -> Optional[Episode]:
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return Episode(**data)
        except Exception as exc:
            print(f"Error reading {path}: {exc}")
            return None

    def _discover_orphan_episodes(self) -> None:
        """Only recover folders that still have video files."""
        try:
            for parent_dir in (EPISODES_DIR, OUTPUT_DIR):
                if not os.path.isdir(parent_dir):
                    continue
                for name in os.listdir(parent_dir):
                    folder = os.path.join(parent_dir, name)
                    if not os.path.isdir(folder) or not name.startswith("ep_"):
                        continue
                    path = os.path.join(folder, EPISODE_STATE_FILENAME)
                    if not os.path.isfile(path):
                        continue
                    ep = self._read_episode_file(path)
                    if ep is None or ep.id in self.episodes:
                        continue
                    if not ep.output_folder:
                        ep.output_folder = name
                    if not _episode_has_video_files(ep):
                        continue
                    self.episodes[ep.id] = ep
        except OSError:
            pass

    def _prune_empty_episodes(self, *, persist: bool = False) -> List[str]:
        """Drop non-active episodes with no video; scrub empty ep_* folders."""
        removed: List[str] = []
        for eid, ep in list(self.episodes.items()):
            if _should_keep_episode(ep, self.active_episode_id):
                continue
            removed.append(eid)
            self._purge_episode(eid, ep)

        self._scrub_empty_output_folders()

        if removed and persist:
            self._write_index()
            print(f"Pruned empty episodes: {', '.join(removed)}")
        return removed

    def _scrub_empty_output_folders(self) -> None:
        try:
            tracked_folders = {
                (ep.output_folder or "") for ep in self.episodes.values() if ep.output_folder
            }
            for parent_dir in (EPISODES_DIR, OUTPUT_DIR):
                if not os.path.isdir(parent_dir):
                    continue
                for name in list(os.listdir(parent_dir)):
                    if not name.startswith("ep_"):
                        continue
                    folder = os.path.join(parent_dir, name)
                    if not os.path.isdir(folder):
                        continue
                    has_video = False
                    try:
                        for root, _, files in os.walk(folder):
                            for fname in files:
                                if os.path.splitext(fname)[1].lower() in _VIDEO_EXTS:
                                    has_video = True
                                    break
                            if has_video:
                                break
                    except OSError:
                        continue
                    if has_video:
                        continue
                    if name in tracked_folders:
                        continue
                    shutil.rmtree(folder, ignore_errors=True)
                    print(f"  scrubbed empty folder: {name}")
        except OSError:
            pass

    def _purge_episode(self, eid: str, ep: Optional[Episode]) -> None:
        self.episodes.pop(eid, None)
        if ep is not None:
            folder = _episode_folder_path(ep)
            if os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)

    def _migrate_legacy_monolith(self) -> None:
        print(f"Migrating {LEGACY_STATE_FILE} → per-episode episode.json + pipeline_index.json")
        with open(LEGACY_STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        self.active_episode_id = data.get("active_episode_id")
        for _ep_id, ep_dict in (data.get("episodes") or {}).items():
            ep = Episode(**ep_dict)
            if not ep.output_folder:
                ep.output_folder = resolve_episode_folder(ep.id, ep.title)
            if not _should_keep_episode(ep, self.active_episode_id):
                continue
            _ensure_episode_dir(ep)
            _atomic_write_json(episode_state_path(ep), ep.dict())
            self.episodes[ep.id] = ep
            print(f"  wrote {ep.output_folder}/{EPISODE_STATE_FILENAME}")

        self._write_index()
        try:
            os.remove(LEGACY_STATE_FILE)
            print(f"  removed {LEGACY_STATE_FILE}")
        except OSError as exc:
            print(f"  warning: could not delete monolith: {exc}")

    def _write_index(self) -> None:
        # Index only lists kept episodes (video present, or active draft).
        kept = {
            ep_id: ep
            for ep_id, ep in self.episodes.items()
            if _should_keep_episode(ep, self.active_episode_id)
        }
        self.episodes = kept
        if self.active_episode_id not in self.episodes:
            self.active_episode_id = self._preferred_active_id()
        payload = {
            "active_episode_id": self.active_episode_id,
            "episodes": {ep_id: _index_entry(ep) for ep_id, ep in self.episodes.items()},
        }
        _atomic_write_json(INDEX_FILE, payload)

    def _write_episode(self, ep: Episode) -> None:
        if not _should_keep_episode(ep, self.active_episode_id):
            return
        ep.updated_at = time.time()
        if not ep.output_folder:
            ep.output_folder = resolve_episode_folder(ep.id, ep.title)
        _ensure_episode_dir(ep)
        _atomic_write_json(episode_state_path(ep), ep.dict())

    def save(self) -> None:
        try:
            _remove_legacy_deleted_file()
            self._prune_empty_episodes(persist=False)
            for ep in list(self.episodes.values()):
                self._write_episode(ep)
            self._write_index()
        except Exception as exc:
            print(f"Error saving state: {exc}")

    def save_episode(self, episode_id: str) -> None:
        try:
            ep = self.episodes.get(episode_id)
            if ep and _should_keep_episode(ep, self.active_episode_id):
                self._write_episode(ep)
            elif ep:
                self._purge_episode(episode_id, ep)
            self._write_index()
        except Exception as exc:
            print(f"Error saving episode {episode_id}: {exc}")

    def get_active_episode(self, user_id: Optional[int] = None) -> Optional[Episode]:
        if user_id is not None:
            # First check if active_episode_id belongs to this user
            if self.active_episode_id and self.active_episode_id in self.episodes:
                ep = self.episodes[self.active_episode_id]
                if ep.user_id == int(user_id):
                    return ep
            # Otherwise return this user's preferred episode
            for ep in self.episodes.values():
                if ep.user_id == int(user_id):
                    folder = _episode_folder_path(ep)
                    if os.path.isfile(os.path.join(folder, "merged_60s.mp4")):
                        return ep
            for ep in self.episodes.values():
                if ep.user_id == int(user_id):
                    return ep
            return None

        if self.active_episode_id and self.active_episode_id in self.episodes:
            return self.episodes[self.active_episode_id]
        if self.episodes:
            self.active_episode_id = self._preferred_active_id()
            return self.episodes.get(self.active_episode_id) if self.active_episode_id else None
        return None

    def create_episode(
        self,
        title: Optional[str] = None,
        engine: str = "mock",
        *,
        catalog_id: Optional[str] = None,
        script_key: str = "hoa_violation",
        episode_number: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Episode:
        from app.engines.factory import engine_display_name, video_engine_mode
        from app.studio.generation import next_episode_number
        from app.studio.naming import make_studio_episode_name

        # Studio queue convention: EP-<serialnumber>-<YYYYMMDD> until pitch confirm.
        target_ep_num = int(episode_number or next_episode_number())
        resolved_title = (title or "").strip() or make_studio_episode_name(serial_number=target_ep_num)

        # Include counter so create+duplicate in the same second never collide.
        base = int(time.time())
        ep_id = f"ep_{base}"
        n = 0
        while ep_id in self.episodes:
            n += 1
            ep_id = f"ep_{base}_{n}"
        taken = {
            (other.output_folder or "").strip()
            for other in self.episodes.values()
            if (other.output_folder or "").strip()
        }
        folder = resolve_episode_folder(ep_id, resolved_title, taken=taken)
        mode = video_engine_mode()
        episode = Episode(
            id=ep_id,
            user_id=user_id,
            title=resolved_title,
            episode_number=target_ep_num,
            output_folder=folder,
            selected_engine=engine or mode,
            final_platform_decision=mode,
            video_engine_used=engine_display_name(),
            status="WAITING_GATEWAY_1",
            production_status="draft",
            current_gateway=1,
            catalog_id=catalog_id,
            script_key=script_key or "hoa_violation",
        )
        _ensure_episode_dir(episode)
        self.episodes[ep_id] = episode
        self.active_episode_id = ep_id
        self.save_episode(ep_id)
        return episode

    def duplicate_episode(self, episode_id: str, user_id: Optional[int] = None) -> Optional[Episode]:
        """Clone episode metadata/script; optionally copy scene media."""
        src = self.episodes.get(episode_id)
        if not src:
            return None
        new_title = f"{src.title} (Copy)"
        clone = self.create_episode(
            title=new_title,
            engine=src.selected_engine or "mock",
            catalog_id=src.catalog_id,
            script_key=src.script_key or "hoa_violation",
            user_id=user_id if user_id is not None else src.user_id,
        )
        clone.available_concepts = list(src.available_concepts or [])
        clone.selected_concept = dict(src.selected_concept) if src.selected_concept else None
        clone.script = dict(src.script) if isinstance(src.script, dict) else src.script
        clone.merch_punchline = src.merch_punchline
        clone.production_status = "draft"
        clone.status = "WAITING_GATEWAY_1"
        clone.current_gateway = 1
        clone.scene_videos = []
        clone.merged_video_url = None
        clone.scenes_merged = False
        clone.clip_history = {}
        clone.generation_jobs = []
        clone.revision_notes = []
        clone.script_versions = list(src.script_versions or [])
        # Copy existing scene mp4s if present so duplicate can preview immediately.
        src_folder = _episode_folder_path(src)
        dst_folder = _episode_folder_path(clone)
        if os.path.isdir(src_folder):
            for name in os.listdir(src_folder):
                if name.startswith("scene_") and name.lower().endswith((".mp4", ".webm")):
                    try:
                        shutil.copy2(
                            os.path.join(src_folder, name),
                            os.path.join(dst_folder, name),
                        )
                    except OSError:
                        pass
        self.save_episode(clone.id)
        return clone

    def rename_episode(self, episode_id: str, title: str) -> Optional[Episode]:
        ep = self.episodes.get(episode_id)
        if not ep:
            return None
        new_title = (title or "").strip() or ep.title
        ep.title = new_title
        # Keep folder stable; only update title field for POC.
        self.save_episode(episode_id)
        return ep

    def list_episodes_sorted(self, user_id: Optional[int] = None) -> List[Episode]:
        from app.studio.generation import ensure_episode_numbers

        ensure_episode_numbers()
        episodes_list = list(self.episodes.values())
        if user_id is not None:
            episodes_list = [e for e in episodes_list if e.user_id == int(user_id)]
        return sorted(
            episodes_list,
            key=lambda e: (
                -(int(getattr(e, "episode_number", 0) or 0)),
                -(float(getattr(e, "updated_at", 0) or 0)),
            ),
        )

    def set_active(self, episode_id: str) -> Optional[Episode]:
        if episode_id not in self.episodes:
            return None
        self.active_episode_id = episode_id
        # Switching away prunes any previous empty draft on save/index write.
        self._prune_empty_episodes(persist=False)
        self._write_index()
        return self.episodes.get(episode_id)

    def delete_episode(self, episode_id: str) -> bool:
        ep = self.episodes.get(episode_id)
        if not ep:
            return False
        self._purge_episode(episode_id, ep)
        if self.active_episode_id == episode_id:
            self.active_episode_id = self._preferred_active_id()
        self._scrub_empty_output_folders()
        self._write_index()
        return True

    def log_qa(self, episode_id: str, message: str) -> None:
        ep = self.episodes.get(episode_id)
        if ep:
            timestamp = time.strftime("%H:%M:%S")
            ep.qa_logs.append(f"[{timestamp}] {message}")
            self.save_episode(episode_id)


state_manager = StateManager()
