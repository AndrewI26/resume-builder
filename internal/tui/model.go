package tui

import (
	"fmt"
	"path/filepath"
	"time"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/textarea"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Model is the root Bubble Tea model for the file browser + editor TUI.
type Model struct {
	root   string
	cwd    string
	width  int
	height int

	focus pane
	list  list.Model
	ta    textarea.Model

	editorPath  string
	diskContent string
	statusMsg   string

	// At most one checked entry per subheading group (UI only): directories vs files.
	checkedDir  string // absolute path under "Directories", empty if none
	checkedFile string // absolute path under "Files", empty if none

	// saveGen increments on each editor keystroke; debounced autosave only runs for the latest generation.
	saveGen int
}

// debouncedSaveMsg triggers a delayed write after typing pauses.
type debouncedSaveMsg struct{ gen int }

type pane int

const (
	paneList pane = iota
	paneEditor
)

var (
	borderActive   = lipgloss.Color("99")
	borderInactive = lipgloss.Color("238")
	statusStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("244"))
)

// New builds the program model rooted at an absolute directory path.
func New(root string) (*Model, error) {
	root = filepath.Clean(root)
	items, err := readDirItems(root, root)
	if err != nil {
		return nil, err
	}

	m := &Model{
		root:   root,
		cwd:    root,
		width:  80,
		height: 24,
		focus:  paneList,
	}

	del := newFileListDelegate(func(path string) bool {
		return path != "" && (path == m.checkedDir || path == m.checkedFile)
	})

	l := list.New(items, del, 0, 0)
	l.Title = shortPath(root)
	l.DisableQuitKeybindings()
	l.SetShowStatusBar(true)
	l.SetFilteringEnabled(true)
	l.SetShowPagination(true)

	t := textarea.New()
	t.Placeholder = "Open a file from the list on the left (Enter). Tab switches panes."
	t.ShowLineNumbers = false
	focusedStyle, blurredStyle := textarea.DefaultStyles()
	// Default focused CursorLine uses a full-row background (reads as a solid block).
	focusedStyle.CursorLine = focusedStyle.Text
	blurredStyle.CursorLine = blurredStyle.Text
	t.FocusedStyle = focusedStyle
	t.BlurredStyle = blurredStyle
	// Caret: thin foreground bar (reverse-video cell) instead of a wide block look.
	t.Cursor.Style = lipgloss.NewStyle().Foreground(lipgloss.AdaptiveColor{Light: "0", Dark: "7"})
	t.Cursor.TextStyle = lipgloss.NewStyle().Foreground(lipgloss.AdaptiveColor{Light: "0", Dark: "7"})
	t.Blur()

	m.list = l
	m.ta = t
	m.list.Filter = m.filterWithoutHeadingItems
	m.skipHeadingRows(false)
	m.syncSizes()
	return m, nil
}

// Init implements tea.Model.
func (m *Model) Init() tea.Cmd {
	return nil
}

func scheduleDebouncedSave(gen int) tea.Cmd {
	return tea.Tick(450*time.Millisecond, func(time.Time) tea.Msg {
		return debouncedSaveMsg{gen: gen}
	})
}

// Update implements tea.Model.
func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case debouncedSaveMsg:
		if msg.gen != m.saveGen {
			return m, nil
		}
		if m.editorPath == "" || !m.dirty() {
			return m, nil
		}
		return m.doSave(false)

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.syncSizes()
		var lcmd, tcmd tea.Cmd
		m.list, lcmd = m.list.Update(msg)
		m.ta, tcmd = m.ta.Update(msg)
		if m.focus == paneList {
			m.skipHeadingRows(false)
		}
		return m, tea.Batch(lcmd, tcmd)

	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c":
			return m, tea.Quit
		}

		if msg.String() == "tab" {
			if m.focus == paneList && m.list.FilterState() == list.Filtering {
				var cmd tea.Cmd
				m.list, cmd = m.list.Update(msg)
				return m, cmd
			}
			cmd := m.toggleFocus()
			return m, cmd
		}

		// Ctrl+S is often eaten by the terminal (XOFF). Ctrl+O is a reliable alternative (like nano).
		if (msg.String() == "ctrl+s" || msg.String() == "ctrl+o") && m.editorPath != "" {
			return m.save()
		}
		if msg.String() == "ctrl+r" && m.editorPath != "" {
			return m.revert()
		}

		if m.focus == paneList {
			if msg.String() == "enter" && m.list.FilterState() != list.Filtering {
				return m.openSelected()
			}
			// Toggle checkmark on file/dir rows (not headings or ".."). Space while filtering goes to the filter field.
			if msg.String() == " " && m.list.FilterState() != list.Filtering {
				m.toggleCheckSelected()
				return m, nil
			}
			var cmd tea.Cmd
			m.list, cmd = m.list.Update(msg)
			m.skipHeadingForKey(msg.String())
			return m, cmd
		}

		var cmd tea.Cmd
		m.ta, cmd = m.ta.Update(msg)
		if m.editorPath != "" {
			m.saveGen++
			g := m.saveGen
			return m, tea.Batch(cmd, scheduleDebouncedSave(g))
		}
		return m, cmd

	default:
		var lcmd, tcmd tea.Cmd
		m.list, lcmd = m.list.Update(msg)
		m.ta, tcmd = m.ta.Update(msg)
		if m.focus == paneList {
			m.skipHeadingRows(false)
		}
		return m, tea.Batch(lcmd, tcmd)
	}
}

// View implements tea.Model.
func (m *Model) View() string {
	if m.width <= 0 {
		m.width = 80
	}
	if m.height <= 0 {
		m.height = 24
	}

	contentH := m.height - 1
	if contentH < 3 {
		contentH = 3
	}

	listOuter, editorOuter := m.splitWidths()

	listBorder := lipgloss.RoundedBorder()
	listFrame := lipgloss.NewStyle().
		Width(listOuter).
		Height(contentH).
		Border(listBorder).
		BorderForeground(borderInactive)
	if m.focus == paneList {
		listFrame = listFrame.BorderForeground(borderActive)
	}
	files := listFrame.Render(m.list.View())

	edBorder := lipgloss.RoundedBorder()
	edFrame := lipgloss.NewStyle().
		Width(editorOuter).
		Height(contentH).
		Border(edBorder).
		BorderForeground(borderInactive)
	if m.focus == paneEditor {
		edFrame = edFrame.BorderForeground(borderActive)
	}
	editor := edFrame.Render(m.ta.View())

	body := lipgloss.JoinHorizontal(lipgloss.Top, files, editor)

	statusText := m.statusLine()
	if len(statusText) > m.width && m.width > 3 {
		statusText = statusText[:m.width-3] + "..."
	}
	status := statusStyle.Width(m.width).Render(statusText)

	return lipgloss.JoinVertical(lipgloss.Left, body, status)
}

func (m *Model) statusLine() string {
	if m.statusMsg != "" {
		return m.statusMsg
	}
	return "Tab: panes  Space: check (one per section)  /: filter  Enter: open  Ctrl+O: save  Ctrl+R: revert  Ctrl+C: quit"
}

// splitWidths returns outer column widths: narrow file list (left), wide editor (right).
func (m *Model) splitWidths() (listOuter, editorOuter int) {
	listOuter = (m.width * 36) / 100
	if listOuter < 24 {
		listOuter = 24
	}
	if listOuter > m.width-12 {
		listOuter = m.width / 3
	}
	editorOuter = m.width - listOuter - 1
	if editorOuter < 12 {
		editorOuter = 12
	}
	return listOuter, editorOuter
}

func (m *Model) syncSizes() {
	contentH := m.height - 1
	if contentH < 3 {
		contentH = 3
	}
	listOuter, editorOuter := m.splitWidths()
	innerListW := listOuter - 2
	innerListH := contentH - 2
	if innerListW < 8 {
		innerListW = 8
	}
	if innerListH < 3 {
		innerListH = 3
	}
	m.list.SetSize(innerListW, innerListH)

	innerEdW := editorOuter - 4
	innerEdH := contentH - 2
	if innerEdW < 8 {
		innerEdW = 8
	}
	if innerEdH < 3 {
		innerEdH = 3
	}
	m.ta.SetWidth(innerEdW)
	m.ta.SetHeight(innerEdH)
}

func (m *Model) toggleCheckSelected() {
	it := m.list.SelectedItem()
	if it == nil {
		return
	}
	fi, ok := it.(fileItem)
	if !ok || fi.title == ".." {
		return
	}
	if fi.isDir {
		if m.checkedDir == fi.path {
			m.checkedDir = ""
		} else {
			m.checkedDir = fi.path
		}
		return
	}
	if m.checkedFile == fi.path {
		m.checkedFile = ""
	} else {
		m.checkedFile = fi.path
	}
}

func (m *Model) toggleFocus() tea.Cmd {
	if m.focus == paneList {
		m.focus = paneEditor
		return m.ta.Focus()
	}
	m.focus = paneList
	m.ta.Blur()
	return nil
}

// filterWithoutHeadingItems wraps the default fuzzy filter and removes section headings from results.
func (m *Model) filterWithoutHeadingItems(term string, targets []string) []list.Rank {
	ranks := list.DefaultFilter(term, targets)
	items := m.list.Items()
	var out []list.Rank
	for _, r := range ranks {
		if r.Index < 0 || r.Index >= len(items) {
			continue
		}
		if _, ok := items[r.Index].(headingItem); ok {
			continue
		}
		out = append(out, r)
	}
	return out
}

// skipHeadingForKey moves the cursor off heading rows after navigation (headings are not selectable).
func (m *Model) skipHeadingForKey(keyStr string) {
	preferUp := keyStr == "up" || keyStr == "k" || keyStr == "ctrl+p"
	m.skipHeadingRows(preferUp)
}

func (m *Model) skipHeadingRows(preferUp bool) {
	const maxIter = 500
	for i := 0; i < maxIter; i++ {
		it := m.list.SelectedItem()
		if it == nil {
			return
		}
		if _, ok := it.(headingItem); !ok {
			return
		}
		n := len(m.list.Items())
		if n == 0 {
			return
		}
		idx := m.list.Index()
		if preferUp {
			if idx > 0 {
				m.list.CursorUp()
			} else if n > 1 {
				m.list.CursorDown()
				preferUp = false
			} else {
				return
			}
		} else {
			if idx < n-1 {
				m.list.CursorDown()
			} else if idx > 0 {
				m.list.CursorUp()
			} else {
				return
			}
		}
	}
}

func (m *Model) dirty() bool {
	if m.editorPath == "" {
		return false
	}
	return m.ta.Value() != m.diskContent
}

func (m *Model) openSelected() (tea.Model, tea.Cmd) {
	it := m.list.SelectedItem()
	if it == nil {
		return m, nil
	}
	if IsHeading(it) {
		return m, nil
	}
	item, ok := it.(fileItem)
	if !ok {
		return m, nil
	}

	if item.isDir {
		newCwd := filepath.Clean(item.path)
		if !containedInRoot(newCwd, m.root) {
			m.statusMsg = "cannot navigate outside browse root"
			return m, nil
		}
		m.cwd = newCwd
		items, err := readDirItems(m.cwd, m.root)
		if err != nil {
			m.statusMsg = err.Error()
			return m, nil
		}
		m.checkedDir, m.checkedFile = "", ""
		m.list.Title = shortPath(m.cwd)
		cmd := m.list.SetItems(items)
		m.skipHeadingRows(false)
		m.statusMsg = ""
		return m, cmd
	}

	if m.dirty() {
		m.statusMsg = "unsaved changes — save (Ctrl+S) or revert (Ctrl+R) in editor first"
		return m, nil
	}

	s, err := loadFile(item.path)
	if err != nil {
		m.statusMsg = err.Error()
		return m, nil
	}
	m.editorPath = item.path
	m.diskContent = s
	m.ta.SetValue(s)
	m.statusMsg = "loaded " + filepath.Base(item.path)
	m.focus = paneEditor
	return m, m.ta.Focus()
}

func (m *Model) save() (tea.Model, tea.Cmd) {
	return m.doSave(true)
}

func (m *Model) doSave(verbose bool) (tea.Model, tea.Cmd) {
	if m.editorPath == "" {
		if verbose {
			m.statusMsg = "no file open in editor"
		}
		return m, nil
	}
	if err := saveFile(m.editorPath, m.ta.Value()); err != nil {
		m.statusMsg = fmt.Sprintf("save: %v", err)
		return m, nil
	}
	m.diskContent = m.ta.Value()
	if verbose {
		m.statusMsg = "saved " + filepath.Base(m.editorPath)
	}
	return m, nil
}

func (m *Model) revert() (tea.Model, tea.Cmd) {
	if m.editorPath == "" {
		return m, nil
	}
	m.ta.SetValue(m.diskContent)
	m.statusMsg = "reverted to last loaded/saved content"
	return m, nil
}

func shortPath(dir string) string {
	dir = filepath.Clean(dir)
	const max = 36
	if len(dir) <= max {
		return dir
	}
	return "…" + dir[len(dir)-(max-1):]
}
