import bar_chart_race as bcr
import pandas as pd
import sys


def main(sourceData='out/data.csv'):
    df = pd.read_csv(sourceData, index_col='date')
    df.fillna(0,inplace=True)

    try:
        bcr.bar_chart_race(
        # must be a DataFrame where each row represents a single period of time.
        df=df,

        # name of the video file
        filename="out/video.mp4",

        # specify location of image folder if you want image labels for each bar
        # img_label_folder="bar_image_labels",
        # this is only on programiz version of the library

        # change the Figure properties
        fig_kwargs={
            'figsize': (16, 9),
            'dpi': 120,
            'facecolor': '#F8FAFF'
        },

        # smoothness of the animation (lines per step)
        steps_per_period=20,

        # number of bars to display in each frame
        n_bars=30,

        # time period in ms for each line
        # video length = rows * period_length
        period_length=500,

        # custom set of colors
        colors=[
            '#6ECBCE', '#FF2243', '#FFC33D', '#CE9673', '#FFA0FF', '#6501E5', '#F79522', '#699AF8', '#34718E', '#00DBCD',
            '#00A3FF', '#F8A737', '#56BD5B', '#D40CE5', '#6936F9', '#FF317B', '#0000F3', '#FFA0A0', '#31FF83', '#0556F3'
        ],

        # title and its styles
        title={'label': 'Commits by Author',
               'size': 40,
               'weight': 'bold',
               'pad': 15
               },

        filter_column_colors=True,

        # **** less common settings (keep default unless you must change): ****
        # orientation of the bar: h or v
        orientation="h",
        # sort the bar for each period
        sort="desc",

        # to fix the maximum value of the axis
        fixed_max=False,

        # adjust the position and style of the period label
        period_label={'x': .95, 'y': .15,
                      'ha': 'right',
                      'va': 'center',
                      'size': 35,
                      'weight': 'semibold'
                      },

        # style the bar label text
        bar_label_font={'size': 17},

        # style the labels in x and y axis
        tick_label_font={'size': 17},

        # adjust the style of bar
        # alpha is opacity of bar
        # ls - width of edge
        bar_kwargs={'alpha': .99, 'lw': 0},

        # check these later, they are crashing on current python3 version
        # # adjust the bar label format
        # bar_texttemplate='{x:.2f}',

        # # adjust the period label format
        # period_template='{x:.0f}',
        )
    except Exception as e:
        import traceback as tb
        tb.print_exc()
        import IPython; IPython.embed()
    
    return 0

if __name__ == '__main__':
    if (len(sys.argv) == 1):
        print('using default path (probably out/data.csv)')
    if (len(sys.argv) > 2):
        print('usage: {} [source csv path]'.format(os.path.basename(argv[0])))
        sys.exit(-1)
    sys.exit(main(*sys.argv[1:]))