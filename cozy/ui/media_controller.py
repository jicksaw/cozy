import logging

import inject
from gi.repository import Adw, Gdk, Gtk

from cozy.control.artwork_cache import ArtworkCache
from cozy.db.book import Book
from cozy.ui.widgets.playback_speed_popover import PlaybackSpeedPopover
from cozy.ui.widgets.seek_bar import SeekBar
from cozy.ui.widgets.sleep_timer import SleepTimer
from cozy.view_model.playback_control_view_model import PlaybackControlViewModel
from cozy.view_model.playback_speed_view_model import PlaybackSpeedViewModel

log = logging.getLogger("MediaController")

COVER_SIZE = 46


@Gtk.Template.from_resource("/com/github/geigi/cozy/ui/media_controller.ui")
class MediaController(Adw.BreakpointBin):
    __gtype_name__ = "MediaController"

    seek_bar_container: Gtk.Box = Gtk.Template.Child()

    play_button: Gtk.Button = Gtk.Template.Child()
    prev_button: Gtk.Button = Gtk.Template.Child()
    next_button: Gtk.Button = Gtk.Template.Child()
    volume_button: Gtk.ScaleButton = Gtk.Template.Child()

    cover_img: Gtk.Image = Gtk.Template.Child()
    title_label: Gtk.Label = Gtk.Template.Child()
    subtitle_label: Gtk.Label = Gtk.Template.Child()

    playback_speed_button: Gtk.MenuButton = Gtk.Template.Child()
    timer_button: Gtk.MenuButton = Gtk.Template.Child()

    timer_image: Gtk.Image = Gtk.Template.Child()

    def __init__(self, main_window_builder: Gtk.Builder):
        super().__init__()

        self.container_bar: Gtk.Revealer = main_window_builder.get_object("media_control_box")
        self.container_bar.set_child(self)

        self.seek_bar = SeekBar()
        self.seek_bar_container.append(self.seek_bar)

        self.sleep_timer = SleepTimer(self.timer_button)
        self.timer_button.connect("clicked", self.sleep_timer.present)
        self.playback_speed_button.set_popover(PlaybackSpeedPopover())

        self.volume_button.set_icons(
            [
                "audio-volume-muted-symbolic",
                "audio-volume-high-symbolic",
                "audio-volume-low-symbolic",
                "audio-volume-medium-symbolic",
            ]
        )

        self._playback_control_view_model = inject.instance(PlaybackControlViewModel)
        self._playback_speed_view_model = inject.instance(PlaybackSpeedViewModel)
        self._artwork_cache: ArtworkCache = inject.instance(ArtworkCache)
        self._connect_view_model()
        self._connect_widgets()

        self._on_book_changed()
        self._on_lock_ui_changed()
        self._on_length_changed()
        self._on_position_changed()
        self._on_volume_changed()
        self._setup_shortcuts()

    def _connect_view_model(self):
        self._playback_control_view_model.bind_to("book", self._on_book_changed)
        self._playback_control_view_model.bind_to("playing", self._on_play_changed)
        self._playback_control_view_model.bind_to("length", self._on_length_changed)
        self._playback_control_view_model.bind_to("position", self._on_position_changed)
        self._playback_control_view_model.bind_to("lock_ui", self._on_lock_ui_changed)
        self._playback_control_view_model.bind_to("volume", self._on_volume_changed)

    def _connect_widgets(self):
        self.play_button.connect("clicked", self._play_clicked)
        self.volume_button.connect("value-changed", self._on_volume_button_changed)
        self.seek_bar.connect("position-changed", self._on_seek_bar_position_changed)

        self.prev_button.connect("clicked", self._rewind_clicked)
        self.next_button.connect("clicked", self._forward_clicked)
        self.seek_bar.connect("rewind", self._rewind_clicked)
        self.seek_bar.connect("forward", self._forward_clicked)

        cover_click_gesture = Gtk.GestureClick()
        cover_click_gesture.connect("pressed", self._cover_clicked)
        self.cover_img.add_controller(cover_click_gesture)
        self.cover_img.set_cursor(Gdk.Cursor.new_from_name("pointer"))

    def _set_cover_image(self, book: Book):
        paintable = self._artwork_cache.get_cover_paintable(
            book, self.get_scale_factor(), COVER_SIZE
        )
        if paintable:
            self.cover_img.set_from_paintable(paintable)
        else:
            self.cover_img.set_from_icon_name("book-open-variant-symbolic")
            self.cover_img.props.pixel_size = COVER_SIZE

    @inject.param("main_window", "MainWindow")
    def _setup_shortcuts(self, main_window):
        main_window.create_action("play_pause", self._play_clicked, ["space"])
        main_window.create_action("seek_rewind", self._rewind_clicked, ["Left"])
        main_window.create_action("seek_forward", self._forward_clicked, ["Right"])

        main_window.create_action("volume_up", self._volume_up, ["Up"])
        main_window.create_action("volume_down", self._volume_down, ["Down"])

        main_window.create_action("speed_up", self._speed_up, ["plus", "KP_Add", "<primary>Up"])
        main_window.create_action("speed_down", self._speed_down, ["minus", "KP_Subtract", "<primary>Down"])
        main_window.create_action("speed_reset", self._speed_reset, ["equal"])

        main_window.create_action("prev_chapter", self._prev_chapter, ["Page_Down", "<primary>Left"])
        main_window.create_action("next_chapter", self._next_chapter, ["Page_Up", "<primary>Right"])

    def _on_book_changed(self) -> None:
        book = self._playback_control_view_model.book
        self._set_book(book)
        self._show_media_information(bool(book))

    def _show_media_information(self, visibility: bool) -> None:
        self.title_label.set_visible(visibility)
        self.subtitle_label.set_visible(visibility)
        self.cover_img.set_visible(visibility)
        self.seek_bar.visible = visibility

    def _set_book(self, book: Book) -> None:
        if book is not None:
            self._set_cover_image(book)
            self.title_label.set_text(book.name)
            self.title_label.set_tooltip_text(book.name)
            self.subtitle_label.set_text(book.current_chapter.name)
            self.subtitle_label.set_tooltip_text(book.current_chapter.name)

    def _on_play_changed(self):
        if self._playback_control_view_model.playing:
            self.play_button.set_icon_name("media-playback-pause-symbolic")
        else:
            self.play_button.set_icon_name("media-playback-start-symbolic")

    def _on_position_changed(self):
        position = self._playback_control_view_model.relative_position
        if position is not None:
            self.seek_bar.position = position

    def _on_length_changed(self):
        length = self._playback_control_view_model.length
        if length:
            self.seek_bar.length = length

    def _on_lock_ui_changed(self):
        sensitive = not self._playback_control_view_model.lock_ui
        self.container_bar.set_reveal_child(sensitive)

    def _on_volume_changed(self):
        self.volume_button.set_value(self._playback_control_view_model.volume)

    def _volume_up(self, *_):
        self._playback_control_view_model.volume_up()

    def _volume_down(self, *_):
        self._playback_control_view_model.volume_down()

    def _speed_up(self, *_):
        self._playback_speed_view_model.speed_up()

    def _speed_down(self, *_):
        self._playback_speed_view_model.speed_down()

    def _speed_reset(self, *_):
        self._playback_speed_view_model.speed_reset()

    def _next_chapter(self, *_):
        self._playback_control_view_model.next_chapter()

    def _prev_chapter(self, *_):
        self._playback_control_view_model.previous_chapter()

    def _play_clicked(self, *_):
        self._playback_control_view_model.play_pause()

    def _rewind_clicked(self, *_):
        self._playback_control_view_model.rewind()

    def _forward_clicked(self, *_):
        self._playback_control_view_model.forward()

    def _cover_clicked(self, *_):
        self._playback_control_view_model.open_book_detail()

    def _on_volume_button_changed(self, _, volume):
        self._playback_control_view_model.volume = volume

    def _on_seek_bar_position_changed(self, _, position):
        self._playback_control_view_model.relative_position = position
