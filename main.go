package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"

	tea "github.com/charmbracelet/bubbletea"

	"resume-builder/internal/resume"
	"resume-builder/internal/tui"
)

func main() {
	rootFlag := flag.String("path", ".", "directory to browse (root); navigation stays within this tree")
	renderConfigFlag := flag.String("render-config", "", "path to versioned resume JSON config; when set, runs template rendering mode")
	templateFlag := flag.String("template", "blank_resume.tex.go.tmpl", "path to LaTeX Go template file")
	outputFlag := flag.String("out", "generated_resume.tex", "output .tex path for render mode")
	flag.Parse()

	if *renderConfigFlag != "" {
		if err := resume.RenderFromConfig(*renderConfigFlag, *templateFlag, *outputFlag); err != nil {
			log.Fatal(err)
		}
		fmt.Println("generated:", *outputFlag)
		return
	}

	root, err := filepath.Abs(*rootFlag)
	if err != nil {
		log.Fatal(err)
	}
	st, err := os.Stat(root)
	if err != nil {
		log.Fatal(err)
	}
	if !st.IsDir() {
		fmt.Fprintln(os.Stderr, "not a directory:", root)
		os.Exit(1)
	}

	m, err := tui.New(root)
	if err != nil {
		log.Fatal(err)
	}

	p := tea.NewProgram(m, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		log.Fatal(err)
	}
}
