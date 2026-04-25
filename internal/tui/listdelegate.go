package tui

import (
	"fmt"
	"io"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"
)

// fileListDelegate renders section headings and file rows with optional checkmarks.
type fileListDelegate struct {
	def list.DefaultDelegate
	// isChecked returns whether the absolute path is marked (nil = never checked).
	isChecked func(string) bool
}

func newFileListDelegate(isChecked func(string) bool) *fileListDelegate {
	d := list.NewDefaultDelegate()
	d.ShowDescription = false
	return &fileListDelegate{def: d, isChecked: isChecked}
}

func (f *fileListDelegate) Height() int {
	return f.def.Height()
}

func (f *fileListDelegate) Spacing() int {
	return f.def.Spacing()
}

func (f *fileListDelegate) Update(msg tea.Msg, m *list.Model) tea.Cmd {
	return f.def.Update(msg, m)
}

func (f *fileListDelegate) Render(w io.Writer, m list.Model, index int, item list.Item) {
	if h, ok := item.(headingItem); ok {
		st := lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.AdaptiveColor{Light: "120", Dark: "145"})
		_, _ = io.WriteString(w, st.Render("  "+h.label))
		return
	}
	if fi, ok := item.(fileItem); ok && fi.title != ".." {
		checked := f.isChecked != nil && f.isChecked(fi.path)
		renderFileItemWithCheck(f, w, m, index, fi, checked)
		return
	}
	f.def.Render(w, m, index, item)
}

// renderFileItemWithCheck mirrors list.DefaultDelegate single-line rendering with a leading [✓]/[ ] column.
func renderFileItemWithCheck(f *fileListDelegate, w io.Writer, m list.Model, index int, fi fileItem, checked bool) {
	d := &f.def
	s := &d.Styles
	title := fi.Title()

	if m.Width() <= 0 {
		return
	}

	markStr := "[ ] "
	if checked {
		markStr = "[✓] "
	}
	markCol := lipgloss.NewStyle().
		Foreground(lipgloss.AdaptiveColor{Light: "100", Dark: "102"}).
		Render(markStr)
	markW := lipgloss.Width(markCol)

	textwidth := m.Width() - s.NormalTitle.GetPaddingLeft() - s.NormalTitle.GetPaddingRight() - markW
	if textwidth < 1 {
		textwidth = 1
	}
	title = ansi.Truncate(title, textwidth, "…")

	isSelected := index == m.Index()
	emptyFilter := m.FilterState() == list.Filtering && m.FilterValue() == ""
	isFiltered := m.FilterState() == list.Filtering || m.FilterState() == list.FilterApplied

	var matchedRunes []int
	if isFiltered {
		matchedRunes = m.MatchesForItem(index)
	}

	if emptyFilter {
		title = s.DimmedTitle.Render(title)
	} else if isSelected && m.FilterState() != list.Filtering {
		if isFiltered && len(matchedRunes) > 0 {
			unmatched := s.SelectedTitle.Inline(true)
			matched := unmatched.Inherit(s.FilterMatch)
			title = lipgloss.StyleRunes(title, matchedRunes, matched, unmatched)
		}
		title = s.SelectedTitle.Render(title)
	} else {
		if isFiltered && len(matchedRunes) > 0 {
			unmatched := s.NormalTitle.Inline(true)
			matched := unmatched.Inherit(s.FilterMatch)
			title = lipgloss.StyleRunes(title, matchedRunes, matched, unmatched)
		}
		title = s.NormalTitle.Render(title)
	}

	_, _ = fmt.Fprintf(w, "%s%s", markCol, title)
}
