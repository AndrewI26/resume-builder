package resume

import (
	"fmt"
	"os"
	"strings"
	"text/template"
)

func RenderFromConfig(configPath, templatePath, outputPath string) error {
	cfg, err := LoadConfig(configPath)
	if err != nil {
		return fmt.Errorf("load config: %w", err)
	}

	data, err := ResolveTemplateData(cfg)
	if err != nil {
		return fmt.Errorf("resolve template data: %w", err)
	}

	funcs := template.FuncMap{
		"latexEscape": latexEscape,
	}
	tpl, err := template.New(templatePath).Funcs(funcs).ParseFiles(templatePath)
	if err != nil {
		return fmt.Errorf("parse template: %w", err)
	}

	f, err := os.Create(outputPath)
	if err != nil {
		return fmt.Errorf("create output: %w", err)
	}
	defer f.Close()

	if err := tpl.Execute(f, data); err != nil {
		return fmt.Errorf("execute template: %w", err)
	}
	return nil
}

func latexEscape(v any) (string, error) {
	s, ok := v.(string)
	if !ok {
		return "", errLatexEscapeInput
	}
	repl := strings.NewReplacer(
		`\\`, `\textbackslash{}`,
		`{`, `\{`,
		`}`, `\}`,
		`$`, `\$`,
		`&`, `\&`,
		`#`, `\#`,
		`_`, `\_`,
		`%`, `\%`,
		`~`, `\textasciitilde{}`,
		`^`, `\textasciicircum{}`,
	)
	return repl.Replace(s), nil
}
