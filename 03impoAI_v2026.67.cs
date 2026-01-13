using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Shapes;
using Windows.UI;

namespace ImpositionStarWinUI3
{
    public class App : Application
    {
        private Window _window;

        public App() { }

        protected override void OnLaunched(LaunchActivatedEventArgs args)
        {
            _window = new MainWindow();
            _window.Activate();
        }
    }

    public class MainWindow : Window
    {
        public MainWindow()
        {
            Title = "Imposition Star – WinUI 3";
            Width = 960;
            Height = 760;

            var rootGrid = new Grid
            {
                Background = new SolidColorBrush(Color.FromArgb(255, 217, 195, 240))
            };

            var rootCard = new Border
            {
                CornerRadius = new CornerRadius(24),
                Background = new SolidColorBrush(Color.FromArgb(255, 245, 236, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(255, 181, 158, 219)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(28),
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
                MaxWidth = 820
            };

            var stack = new StackPanel
            {
                Spacing = 16
            };

            var header = new TextBlock
            {
                Text = "Imposition Star",
                FontSize = 24,
                FontWeight = Windows.UI.Text.FontWeights.SemiBold,
                Foreground = new SolidColorBrush(Color.FromArgb(255, 31, 41, 55))
            };
            stack.Children.Add(header);

            stack.Children.Add(BuildLabeledInput("Folder cu PDF-uri (#N):"));
            stack.Children.Add(BuildLabeledInput("Format coală:"));
            stack.Children.Add(BuildLabeledInput("Gap (mm):"));
            stack.Children.Add(BuildLabeledInput("Cropbox (mm):"));
            stack.Children.Add(BuildLabeledInput("Margine (mm):"));
            stack.Children.Add(BuildLabeledInput("Marginea de jos (mm):"));
            stack.Children.Add(BuildLabeledInput("Bleed (mm) slot:"));
            stack.Children.Add(BuildLabeledInput("Lungime crop (mm):"));
            stack.Children.Add(BuildLabeledInput("Grosime linie crop (mm):"));
            stack.Children.Add(BuildLabeledInput("Scalare piese (%):"));

            var actionRow = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                Spacing = 12,
                HorizontalAlignment = HorizontalAlignment.Right
            };

            actionRow.Children.Add(BuildPrimaryButton("Generează VARIANTE (preview)"));
            actionRow.Children.Add(BuildSecondaryButton("Generează PDF final"));
            stack.Children.Add(actionRow);

            rootCard.Child = stack;
            rootGrid.Children.Add(rootCard);
            Content = rootGrid;
        }

        private UIElement BuildLabeledInput(string label)
        {
            var container = new StackPanel { Spacing = 6 };
            container.Children.Add(new TextBlock
            {
                Text = label,
                FontSize = 16,
                FontWeight = Windows.UI.Text.FontWeights.SemiBold,
                Foreground = new SolidColorBrush(Color.FromArgb(255, 31, 41, 55))
            });

            var input = new TextBox
            {
                CornerRadius = new CornerRadius(12),
                Padding = new Thickness(12, 8, 12, 8),
                FontSize = 16,
                BorderBrush = new SolidColorBrush(Color.FromArgb(255, 181, 158, 219)),
                BorderThickness = new Thickness(1),
                Background = new SolidColorBrush(Colors.White)
            };
            container.Children.Add(input);
            return container;
        }

        private Button BuildPrimaryButton(string text)
        {
            return new Button
            {
                Content = text,
                CornerRadius = new CornerRadius(14),
                Padding = new Thickness(18, 10, 18, 10),
                FontSize = 16,
                FontWeight = Windows.UI.Text.FontWeights.SemiBold,
                Background = new SolidColorBrush(Color.FromArgb(255, 107, 75, 180)),
                Foreground = new SolidColorBrush(Colors.White)
            };
        }

        private Button BuildSecondaryButton(string text)
        {
            return new Button
            {
                Content = text,
                CornerRadius = new CornerRadius(14),
                Padding = new Thickness(18, 10, 18, 10),
                FontSize = 16,
                FontWeight = Windows.UI.Text.FontWeights.SemiBold,
                Background = new SolidColorBrush(Color.FromArgb(255, 233, 221, 255)),
                Foreground = new SolidColorBrush(Color.FromArgb(255, 31, 41, 55))
            };
        }
    }
}
