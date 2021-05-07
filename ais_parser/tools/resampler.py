import numpy
import pandas as pd


def convert_messages_to_hourly_bins(df, period='H', fillnans=False,
                                    run_resample=True):

    if df.empty:
        return df

    if run_resample:

        speed_ts = df.sog.resample(period, how='mean')

        draught_ts = df.draught.resample(period, how=numpy.max)
        df_new = pd.DataFrame({'Speed_Over_Ground': speed_ts, 'Draught': draught_ts})

        for col in df.columns:
            if col != 'Speed_Over_Ground' and col != 'Draught':
                df_new[col] = df[col].resample(period, how='first')

    else:
        df_new = []

    # définir le temps égal à l'index
    df_new['sys_date_time'] = df_new.index.values
    # remplir en avant
    if fillnans:
        # remplir en avant en premier
        df_new = df_new.fillna(method='pad')
        # maintenant remplir en arrière pour rester
        df_new = df_new.fillna(method='bfill')
    else:
        # supprimer toutes les entrées où il y a des nans de vitesse
        df_new = df_new.ix[pd.isnull(df_new.sog) == False]
    return df_new
