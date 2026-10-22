"""Native input sampling without GUI calls or an unbounded queued signal stream."""
from collections import deque
import ctypes
import threading
import time

from gamepad import Mapper, State

DIRECTIONS = frozenset(('up', 'down', 'left', 'right', 'zoom-in', 'zoom-out'))


class GamepadSampler:
    def __init__(self, query, wake, clock=time.monotonic):
        self.query, self.wake, self.clock = query, wake, clock
        self.condition = threading.Condition()
        self.commands = deque(maxlen=32)
        self.epoch = 0
        self.enabled = False
        self.excluded = -1
        self.closed = False
        self.pending = False
        self.ready = False
        self.slot = None
        self.tilt = (0., 0.)
        self.thread = threading.Thread(target=self.run, name='gamepad-sampling', daemon=True)
        self.thread.start()

    def configure(self, enabled, excluded=-1):
        with self.condition:
            self.epoch += 1
            self.enabled, self.excluded = bool(enabled), excluded
            self.commands.clear()
            self.pending = False
            self.ready = False
            self.slot, self.tilt = None, (0., 0.)
            self.condition.notify_all()

    def take(self):
        with self.condition:
            now = self.clock()
            # Never catch up a held direction or execute a stale activation after
            # the GUI was busy. Explicit, recent presses remain ordered.
            commands = [command for at, command, repeat in self.commands if now - at <= .15]
            self.commands.clear()
            self.pending = False
            return self.slot, self.tilt, commands, self.ready

    def publish(self, epoch, slot, tilt, commands, directions=None):
        wake = False
        with self.condition:
            if self.closed or epoch != self.epoch or not self.enabled:
                return
            changed = not self.ready or slot != self.slot or tilt != self.tilt
            self.ready = True
            self.slot, self.tilt = slot, tilt
            if directions is not None:
                self.commands = deque((row for row in self.commands if not row[2] or row[1] in directions), maxlen=32)
            for at, command, repeat in commands:
                if command in DIRECTIONS:
                    # One outstanding held-repeat per axis. Direction changes
                    # discard obsolete held repeats, without losing fresh taps.
                    zoom = command.startswith('zoom-')
                    self.commands = deque((row for row in self.commands if not (row[2] and row[1].startswith('zoom-') == zoom)), maxlen=32)
                self.commands.append((at, command, repeat))
            if (changed or commands) and not self.pending:
                self.pending = True
                wake = True
        if wake:
            self.wake()

    def run(self):
        epoch = -1
        mapper = Mapper()
        slot = None
        while True:
            with self.condition:
                while not self.closed and not self.enabled:
                    self.condition.wait()
                if self.closed:
                    return
                current, excluded = self.epoch, self.excluded
            if current != epoch:
                epoch = current
                slot = None
                mapper.reset()
            found = None
            for index in ([slot] if slot is not None else range(4)):
                if index == excluded:
                    continue
                state = State()
                try:
                    status=self.query(index, ctypes.byref(state))
                except (OSError, ctypes.ArgumentError):
                    status=1167
                if status == 0:
                    found = (index, state.pad)
                    break
            if found:
                index, pad = found
                if slot is None:
                    mapper.reset()
                    mapper.buttons = pad.buttons  # Held A on resume is not a press.
                slot = index
                now = self.clock()
                previous, previous_zoom = mapper.direction, mapper.zoom_direction
                commands = [(now, command, command == (previous_zoom if command.startswith('zoom-') else previous) and command in DIRECTIONS)
                            for command in mapper.read(pad, now)]
                def axis(value):
                    return round((1 if value > 0 else -1) * max(0, (abs(value) / 32767 - .12) / .88), 3)
                self.publish(epoch, slot, (axis(pad.rx), axis(pad.ry)), commands, (mapper.direction, mapper.zoom_direction))
            else:
                slot = None
                mapper.reset()
                self.publish(epoch, None, (0., 0.), [])
            with self.condition:
                if self.closed:
                    return
                if epoch == self.epoch:
                    self.condition.wait(.008 if slot is not None else .35)

    def close(self):
        with self.condition:
            self.closed = True
            self.commands.clear()
            self.condition.notify_all()
        self.thread.join(timeout=2)
