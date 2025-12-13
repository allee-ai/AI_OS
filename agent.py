# agent.py - State Manager for Nola.json

import json
from pathlib import Path
from threading import Lock
import tempfile
import os


STATE_FILE = Path("Nola.json")


class Agent:
	"""Thread-safe state manager for Nola.json.
	
	Provides atomic read/write access to top-level sections of the JSON file.
	Also serves as the chat agent with identity, introspection, and generation.
	"""
	
	def __init__(self, path: Path = STATE_FILE):
		self._path = path
		self._lock = Lock()
		self._state_str = self._load()
	
	@property
	def name(self) -> str:
		"""Return the agent's name from state or default."""
		state = self.get_state()
		identity = state.get("IdentityConfig", {})
		return identity.get("name", "Nola")
	
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
	
	def generate(self, user_input: str, convo: str = "") -> str:
		"""Generate a response to user input using Ollama.
		
		Args:
			user_input: The user's message
			convo: Optional conversation history for context
		
		Returns:
			The agent's response string
		"""
		try:
			import ollama # type: ignore
		except ImportError:
			return "[Error: ollama package not installed. Run: pip install ollama]"
		
		# Build system prompt from state
		state = self.get_state()
		identity = state.get("IdentityConfig", {})
		
		system_prompt = f"""You are {self.name}, a helpful AI assistant.
Your identity config: {json.dumps(identity, indent=2)}

Respond naturally and helpfully to the user."""
		
		# Build messages
		messages = [{"role": "system", "content": system_prompt}]
		
		# Add conversation history if provided
		if convo:
			messages.append({"role": "assistant", "content": f"[Previous conversation context]\n{convo}"})
		
		messages.append({"role": "user", "content": user_input})
		
		try:
			response = ollama.chat(
				model="llama3.2",  # adjust model as needed
				messages=messages
			)
			return response['message']['content']
		except Exception as e:
			return f"[Error generating response: {e}]"


# Module-level singleton instance
agent = Agent()


def get_agent() -> Agent:
	"""Return the module-level Agent singleton."""
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
