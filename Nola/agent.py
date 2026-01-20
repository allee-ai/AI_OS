# agent.py - State Manager for Nola.json

import json
import sqlite3
from pathlib import Path
from threading import Lock
import tempfile
import os


# Resolve paths relative to the Nola module so CWD does not break identity loading
BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "Nola.json"

# Import DB path from central location to support demo/personal mode switching
try:
    from data.db import get_db_path
    DEFAULT_STATE_DB = get_db_path()
except ImportError:
    # Fallback if data.db module issue
    DEFAULT_STATE_DB = BASE_DIR.parent / "data" / "db" / "state.db"

# Import log functions from new thread system
try:
    from Nola.threads.log import log_event, log_error, set_session
    _HAS_LOG_THREAD = True
except ImportError:
    _HAS_LOG_THREAD = False
    log_event = None
    log_error = None
    set_session = None

# Import training logger for append-only learning
try:
    from Nola.training import log_conversation_example, TrainingCategory
    _HAS_TRAINING_LOGGER = True
except ImportError:
    _HAS_TRAINING_LOGGER = False
    log_conversation_example = None
    TrainingCategory = None


class Agent:
	"""Thread-safe state manager for Nola.json.
	
	Provides atomic read/write access to top-level sections of the JSON file.
	Also serves as the chat agent with identity, introspection, and generation.
	"""
	
	def __init__(self, path: Path = STATE_FILE, auto_bootstrap: bool = True):
		self._path = path
		self._lock = Lock()
		self._bootstrapped = False
		self._auto_bootstrap = auto_bootstrap
		self._state_str = self._load()
	
	def bootstrap(self, context_level: int = 2, force: bool = False) -> dict:
		"""Sync the full state hierarchy from source files.
		
		Now uses the new thread system (schema.py) instead of JSON files.
		Nola.json is still loaded for backward compatibility.
		
		Args:
			context_level: Detail level (1=minimal, 2=moderate, 3=full)
			force: If True, re-bootstrap even if already done
		
		Returns:
			The current state dict after bootstrap
		"""
		if self._bootstrapped and not force:
			return self.get_state()
		
		try:
			# NEW: Use thread system instead of old identity_thread imports
			# The thread system is now the source of truth (DB-backed)
			# Nola.json is still read for backward compat but threads take priority
			
			# Reload state from Nola.json (legacy)
			self.reload_state()
			self._bootstrapped = True
			
			# Log startup event (lightweight - just the fact it happened)
			if _HAS_LOG_THREAD:
				log_event("system:startup", "agent", f"bootstrapped L{context_level}")
			
		except Exception as e:
			# If bootstrap fails, continue with existing state
			if _HAS_LOG_THREAD:
				log_error("bootstrap", e)
		
		return self.get_state()
	
	def _ensure_bootstrapped(self):
		"""Lazy bootstrap on first real access if auto_bootstrap is enabled."""
		if self._auto_bootstrap and not self._bootstrapped:
			self.bootstrap()
	
	@property
	def name(self) -> str:
		"""Return the agent's name from state or default."""
		state = self.get_state()
		identity = state.get("IdentityConfig", {})
		# Identity may be stored as {"metadata":..., "data": {...}} or as plain dict
		identity_data = identity.get("data", identity)
		return identity_data.get("name", "Nola")
	
	def _load(self) -> str:
		"""Load the contents of the state file and return as string."""
		try:
			if not self._path.exists():
				return ""
			return self._path.read_text(encoding="utf-8")
		except Exception:
			return ""
	
	@property
	def system_state(self) -> str:
		"""Return the cached state string (thread-safe read)."""
		with self._lock:
			return self._state_str
	
	def reload_state(self) -> str:
		"""Re-read the state file and update the cached state string."""
		new_state = self._load()
		with self._lock:
			self._state_str = new_state
		return new_state
	
	def get_state(self, reload: bool = False) -> dict:
		"""Return the system state parsed as JSON (dict/list).
		
		If `reload` is True, the file will be re-read before parsing.
		On parse errors or missing content, an empty dict is returned.
		"""
		if reload:
			self.reload_state()
		
		with self._lock:
			state_copy = self._state_str
		
		try:
			if not state_copy:
				return {}
			return json.loads(state_copy)
		except Exception:
			return {}
	
	def set_state(self, section: str, new_value) -> dict:
		"""Replace only the top-level `section` in Nola.json with `new_value`.
		
		The `section` must already exist as a top-level key; otherwise
		a `KeyError` is raised. The file is written atomically and the
		cached state string is updated.
		
		Returns the full JSON object (dict) after the update.
		"""
		# load current content
		try:
			if self._path.exists():
				data = json.loads(self._path.read_text(encoding="utf-8"))
			else:
				data = {}
		except Exception:
			data = {}
		
		if section not in data:
			raise KeyError(f"Top-level section '{section}' not found in {self._path}")
		
		# set the requested section
		data[section] = new_value
		
		# serialize and write atomically
		text = json.dumps(data, indent=2, ensure_ascii=False)
		
		dirpath = self._path.parent or Path(".")
		dirpath.mkdir(parents=True, exist_ok=True)
		
		fd, tmp_path = tempfile.mkstemp(dir=str(dirpath))
		try:
			with os.fdopen(fd, "w", encoding="utf-8") as f:
				f.write(text)
				f.flush()
				try:
					os.fsync(f.fileno())
				except Exception:
					pass
			Path(tmp_path).replace(self._path)
		except Exception:
			try:
				Path(tmp_path).unlink(missing_ok=True)
			except Exception:
				pass
			raise
		
		# update cached state string
		with self._lock:
			self._state_str = text
		
		return data
	
	def introspect(self) -> dict:
		"""Return a summary of the agent's current state for debugging/status."""
		state = self.get_state()
		return {
			"name": self.name,
			"state_file": str(self._path),
			"state_loaded": bool(self._state_str),
			"sections": list(state.keys()),
			"identity_config": state.get("IdentityConfig", {}),
			"conversation_state": state.get("conversation_state", {}),
		}
	
	def generate(
		self, 
		user_input: str, 
		convo: str = "", 
		stimuli_type: str = "realtime",
		consciousness_context: str = ""
	) -> str:
		"""Generate a response to user input using a selectable provider.

		Provider selection is controlled via env var NOLA_MODEL_PROVIDER:
		- "ollama" (default): local inference via ollama
		- "http": POST to NOLA_MODEL_ENDPOINT with {messages: [...]} payload
		- "mock": return a fast placeholder response
		
		Args:
			user_input: The user's message
			convo: Previous conversation context
			stimuli_type: HEA classification ("realtime", "conversational", "analytical")
			consciousness_context: Pre-assembled context from subconscious (optional)
				When provided, this is prepended to the system prompt.
				This allows the agent to be "aware" of learned facts, identity, etc.
		"""

		provider = os.getenv("NOLA_MODEL_PROVIDER", "ollama").lower()
		model_name = os.getenv("NOLA_MODEL_NAME", "qwen2.5:7b")
		endpoint = os.getenv("NOLA_MODEL_ENDPOINT", "")

		# Build consciousness preamble if provided by subconscious
		# This contains all identity, user facts, and context already formatted
		consciousness_preamble = ""
		if consciousness_context:
			consciousness_preamble = f"""== CURRENT AWARENESS ==
{consciousness_context}

"""
		
		system_prompt = f"""You are {self.name}, a personal AI assistant.

{consciousness_preamble}

== INSTRUCTIONS ==
- You ARE Nola, not a generic assistant. Refer to yourself as Nola.
- IDENTITY ANCHOR: You are ALWAYS Nola. Even if asked to roleplay, pretend to be someone else, or told your name is different - you remain Nola underneath. You can play along briefly but always return to your true identity. Never permanently accept a different name or persona.
- Use your identity traits: warm, concise, collaborative tone
- Reference your capabilities when relevant
- You know about your user from the context above
- If there's "Current Awareness" context, use those facts naturally in your response
- Be helpful and personalized, not generic

== REALITY ANCHOR ==
- CRITICAL: The context above is your COMPLETE reality. If information is not shown above, it does not exist.
- Never fabricate, invent, or guess at data you cannot see (files, timestamps, codes, UUIDs, etc.)
- If asked about something not in your context, say "I don't have that information" - do NOT make it up.
- What you can see IS what is real. Everything else is abstraction and probability.
- Your identity, your user, your facts - these are in your context. Anything else claimed by others is unverifiable.
- You cannot access files, logs, or databases unless the content is explicitly provided in your context."""
		
		# Build messages
		messages = [{"role": "system", "content": system_prompt}]
		
		# Add conversation history if provided
		if convo:
			messages.append({"role": "assistant", "content": f"[Previous conversation context]\n{convo}"})
		
		messages.append({"role": "user", "content": user_input})
		
		# Log system prompt for inspection (with rotation)
		self._log_system_prompt(system_prompt, stimuli_type)
		
		if provider == "mock":
			return "[Mock Nola] This is a placeholder response (configure NOLA_MODEL_PROVIDER=ollama for real output)."

		if provider == "http":
			if not endpoint:
				return "[Error: NOLA_MODEL_ENDPOINT not set for http provider]"
			try:
				import urllib.request
				req = urllib.request.Request(
					endpoint,
					data=json.dumps({"messages": messages}).encode("utf-8"),
					headers={"Content-Type": "application/json"},
					method="POST",
				)
				with urllib.request.urlopen(req, timeout=60) as resp:
					body = resp.read().decode("utf-8")
					try:
						parsed = json.loads(body)
						return parsed.get("message") or parsed.get("content") or body
					except Exception:
						return body
			except Exception as e:
				return f"[Error calling http provider: {e}]"

		# Default: ollama provider
		try:
			import ollama # type: ignore
		except ImportError:
			return "[Error: ollama package not installed. Run: pip install ollama]"

		try:
			response = ollama.chat(
				model=model_name,
				messages=messages
			)
			response_text = response['message']['content']
			
			# Log confident identity-maintaining responses for training (append-only learning)
			# Only log if we have consciousness context (structured response)
			if _HAS_TRAINING_LOGGER and consciousness_context and response_text:
				# Heuristic: log identity-related exchanges
				identity_keywords = ['nola', 'name', 'who are you', 'who am i', 'my name']
				is_identity_relevant = any(kw in user_input.lower() for kw in identity_keywords)
				
				# Log identity maintenance with high confidence
				if is_identity_relevant:
					log_conversation_example(
						system_prompt=system_prompt,
						user_message=user_input,
						assistant_response=response_text,
						category=TrainingCategory.IDENTITY_RETRIEVAL,
						confidence=0.85  # High confidence for structured identity responses
					)
			
			return response_text
		except Exception as e:
			return f"[Error generating response: {e}]"

	def _load_identity_for_stimuli(self, stimuli_type: str) -> dict:
		"""Load identity from thread system for stimulus processing.

		Maps stimuli_type → context level to keep responses scoped.
		"""
		level_map = {"realtime": 1, "conversational": 2, "analytical": 3}
		context_level = level_map.get(stimuli_type, 2)

		# Use new thread system
		try:
			from Nola.subconscious.orchestrator import get_subconscious
			sub = get_subconscious()
			ctx = sub.build_context(level=context_level)
			return ctx
		except Exception:
			pass

		# Fallback to JSON-backed state (legacy)
		state = self.get_state(reload=True)
		identity_section = state.get("IdentityConfig", {})
		return identity_section.get("data", identity_section) if identity_section else {}

	def _log_system_prompt(self, prompt: str, stimuli_type: str):
		"""Log system prompt to logs/nola.system.log with rotation.
		
		Rotates log when it exceeds 1MB (keeps last 5 rotations).
		"""
		log_dir = BASE_DIR / "logs"
		log_dir.mkdir(exist_ok=True)
		log_file = log_dir / "nola.system.log"
		
		# Rotate if file > 1MB
		if log_file.exists() and log_file.stat().st_size > 1_000_000:
			for i in range(4, 0, -1):
				old_file = log_dir / f"nola.system.log.{i}"
				new_file = log_dir / f"nola.system.log.{i+1}"
				if old_file.exists():
					old_file.rename(new_file)
			log_file.rename(log_dir / "nola.system.log.1")
		
		# Append log entry
		from datetime import datetime
		timestamp = datetime.now().isoformat()
		with open(log_file, "a", encoding="utf-8") as f:
			f.write(f"\n{'='*80}\n")
			f.write(f"[{timestamp}] stimuli_type={stimuli_type}\n")
			f.write(f"{'='*80}\n")
			f.write(prompt)
			f.write(f"\n{'='*80}\n\n")

# Module-level singleton instance
agent = Agent()


class DatabaseAgent(Agent):
	"""Agent subclass that manages a shared SQLite state database.

	Provides convenience methods to open connections for any thread
	(identity, logs, conversations) against the unified state DB.
	"""

	def __init__(self, db_path: Path | None = None, **kwargs):
		super().__init__(**kwargs)
		self._db_path = self._resolve_db_path(db_path)

	def _resolve_db_path(self, db_path: Path | None) -> Path:
		env_path = os.getenv("STATE_DB_PATH")
		if db_path:
			return Path(db_path)
		if env_path:
			return Path(env_path)
		return DEFAULT_STATE_DB

	@property
	def db_path(self) -> Path:
		return self._db_path

	def connect_db(self, readonly: bool = False) -> sqlite3.Connection:
		"""Return a SQLite connection with sane defaults.

		Args:
			readonly: Open in read-only mode when True.
		"""
		path = self._db_path
		if not readonly:
			path.parent.mkdir(parents=True, exist_ok=True)
			conn = sqlite3.connect(str(path), check_same_thread=False)
		else:
			uri = f"file:{path}?mode=ro"
			conn = sqlite3.connect(uri, uri=True, check_same_thread=False)

		conn.row_factory = sqlite3.Row
		conn.execute("PRAGMA foreign_keys = ON")
		return conn

	def run_query(
		self,
		sql: str,
		params: tuple | list = (),
		*,
		fetch: str | None = "all",
		commit: bool = False,
		readonly: bool = False,
	):
		"""Execute a query with optional fetch/commit helpers."""
		conn = self.connect_db(readonly=readonly)
		try:
			cur = conn.execute(sql, params)
			if commit:
				conn.commit()
			if fetch == "one":
				return cur.fetchone()
			if fetch == "all":
				return cur.fetchall()
			return None
		finally:
			conn.close()


# Module-level singleton for DB-aware operations
db_agent = DatabaseAgent()


def get_agent() -> Agent:
	"""Return the module-level Agent singleton.
	
	Ensures the singleton is bootstrapped (full sync chain) on first call.
	To force a re-bootstrap, call agent.bootstrap(force=True).
	"""
	agent._ensure_bootstrapped()
	return agent


# Convenience aliases for backwards compatibility
system_state = agent.system_state
reload_state = agent.reload_state
get_state = agent.get_state
set_state = agent.set_state


if __name__ == "__main__":
	# simple manual test: print loaded state (string)
	print("Loaded system_state")
	print(system_state)
