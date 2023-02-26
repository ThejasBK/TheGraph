from shiny import App, render, ui
import requests
import numpy as np
import pandas as pd
import plotly.express as px
import itertools
import matplotlib.pyplot as plt
import seaborn as sns

api_key = 'e678c81a60b0092baa8c8b79af315192'
url = f'https://gateway.thegraph.com/api/{api_key}/subgraphs/id/GAGwGKc4ArNKKq9eFTcwgd1UGymvqhTier9Npqo1YvZB'

def get_data(query):
    response = requests.post(url=url, json={"query": query.replace('{}', '0').replace('desc', 'asc')})
    data = pd.DataFrame(eval(response.text)['data'])
    for i in range(1000, 5001, 1000):
        response = requests.post(url=url, json={"query": query.replace('{}', str(i))})
        data = pd.concat([data, pd.DataFrame(eval(response.text)['data'])], ignore_index = True)
    return data

def convert(row):
    try:
        return row['name']
    except:
        return np.nan
    
def convert_2(row):
    try:
        return row['lastPriceUSD']
    except:
        return np.nan

deposits_query = """
{
  deposits(orderBy: timestamp, orderDirection: desc, first: 1000, skip: {}) {
    blockNumber
    amountUSD
    from
    hash
    id
    inputTokens {
      lastPriceUSD
      name
    }
    outputToken {
      lastPriceUSD
      name
    }
    protocol {
      network
      schemaVersion
      type
    }
    timestamp
    to
  }
}
"""

financial_query = '''
{
  dexAmmProtocols(first: 1000, skip: {}) {
    id
    financialMetrics(orderBy: timestamp, orderDirection: desc, first: 1000) {
      blockNumber
      cumulativeSupplySideRevenueUSD
      cumulativeTotalRevenueUSD
      cumulativeVolumeUSD
      dailySupplySideRevenueUSD
      dailyTotalRevenueUSD
      dailyVolumeUSD
      id
      timestamp
      totalValueLockedUSD
      cumulativeProtocolSideRevenueUSD
      dailyProtocolSideRevenueUSD
    }
  }
}
'''

dsw_query = '''
{
  events(first: 1000, orderBy: timestamp, orderDirection: desc, skip: {}) {
    id
    timestamp
    to
    ... on Swap {
      id
      amountInUSD
      amountOutUSD
      timestamp
      tokenIn {
        name
        lastPriceUSD
      }
      tokenOut {
        name
        lastPriceUSD
      }
    }
    from
    ... on Deposit {
      id
      amountUSD
      timestamp
      outputToken {
        name
        lastPriceUSD
      }
      inputTokens(first: 1000) {
        lastPriceUSD
        name
      }
    }
    ... on Withdraw {
      id
      amountUSD
      timestamp
      from
      inputTokens {
        name
        lastPriceUSD
      }
      outputToken {
        lastPriceUSD
        name
      }
    }
  }
}
'''

deposits_df = get_data(deposits_query)
deposits_df['amountUSD'] = deposits_df.deposits.apply(lambda row: row['amountUSD'])
deposits_df['id'] = deposits_df.deposits.apply(lambda row: row['id'])
deposits_df['from'] = deposits_df.deposits.apply(lambda row: row['from'])
deposits_df['to'] = deposits_df.deposits.apply(lambda row: row['to'])
deposits_df['blockNumber'] = deposits_df.deposits.apply(lambda row: row['blockNumber'])
deposits_df['timestamp'] = deposits_df.deposits.apply(lambda row: row['timestamp'])
deposits_df['input_last_priceUSD'] = deposits_df.deposits.apply(lambda i: list(map(lambda j: j['lastPriceUSD'], i['inputTokens'])))
deposits_df['output_last_priceUSD'] = deposits_df.deposits.apply(lambda row: row['outputToken']['lastPriceUSD'])
deposits_df['network'] = deposits_df.deposits.apply(lambda row: row['protocol']['network'])
deposits_df['schemaVersion'] = deposits_df.deposits.apply(lambda row: row['protocol']['schemaVersion'])
deposits_df['type'] = deposits_df.deposits.apply(lambda row: row['protocol']['type'])
deposits_df['input_name'] = deposits_df.deposits.apply(lambda i: list(map(lambda j: j['name'], i['inputTokens'])))
deposits_df['output_name'] = deposits_df.deposits.apply(lambda row: row['outputToken']['name'])
deposits_df.drop('deposits', axis = 1, inplace = True)
deposits_df['amountUSD'] = deposits_df['amountUSD'].astype(float)
deposits_df = deposits_df.explode(column = ['input_last_priceUSD', 'input_name'])
deposits_df.drop(['network', 'schemaVersion', 'type'], axis = 1, inplace = True)
u = deposits_df.groupby("id")["input_name"].agg(list)
deposits_df["multi_ids"] = deposits_df["id"].map(u[u.str.len().ge(2)])
deposits_df["multi_ids"].reset_index(drop = True, inplace = True)

financial_data = get_data(financial_query)
financial_data = pd.DataFrame([i for i in map(lambda row: row['financialMetrics'], financial_data['dexAmmProtocols'])][0])

dsw_data = get_data(dsw_query)
dsw_data = pd.DataFrame([i for i in dsw_data['events']])
dsw_data['toekn_in_name'] = dsw_data.tokenIn.apply(convert)
dsw_data['toekn_in_usd'] = dsw_data.tokenIn.apply(convert_2)

dsw_data['toekn_out_name'] = dsw_data.tokenOut.apply(convert)
dsw_data['toekn_out_usd'] = dsw_data.tokenOut.apply(convert_2)
dsw_data.drop(['tokenIn', 'tokenOut'], axis = 1, inplace = True)
swap = dsw_data[dsw_data['id'].apply(lambda row: row.startswith('swap'))][['from', 'timestamp' ,'toekn_in_name', 'toekn_in_usd', 'toekn_out_name', 'toekn_out_usd', 'amountInUSD', 'amountOutUSD']]
swap.amountInUSD = swap.amountInUSD.astype(float)
swap.amountOutUSD = swap.amountOutUSD.astype(float)

app_ui = ui.page_fluid(
    ui.tags.br(),
    ui.h1("Analyzing your Curve Fi data - Live"),
    ui.tags.br(),
    ui.h4("Graph to understand the previous trend"),
    ui.output_text('explain_graph1'),
    ui.output_plot('financial'),
    ui.tags.br(),
    ui.h4("Market Manipulation"),
    ui.output_text('explain_input1'),
    ui.tags.br(),
    ui.input_slider("n", "Number of transactions:", 0, 400, 200),
    ui.output_plot("plot"),
    ui.tags.br(),
    ui.output_text('explain_graph2'),
    ui.tags.br(),
    ui.h4("Relation between Input tokens and Output tokens"),
    ui.output_text('explain_input2'),
    ui.tags.br(),
    ui.input_slider("ip", "Choose the minimum number of input token count:", 0, 2000, 800),
    ui.input_slider("op", "Choose the minimum number of output token count:", 0, 1000, 420),
    ui.output_plot('bar_graph'),
    ui.tags.br(),
    ui.output_text('explain_graph3'),
    ui.tags.br(),
    ui.h4('Most preferred tokens for swapping'),
    ui.output_text('explain_input3'),
    ui.tags.br(),
    ui.input_slider("swap", "Choose the minimum number of input token count:", 0, 150, 70),
    ui.output_plot('swapping'),
    ui.tags.br(),
    ui.output_text('explain_graph4'),
    ui.tags.br(),
)

def server(input, output, session):
    @output
    @render.text
    def explain_graph1():
        return 'The below graph shows the market trend of the curve finance decentralized exchange. The green color shows the Total Value Locked which basically explains the market trend. As this alone cannnot be used to understand the market, we plot the orange area color that explains the volume traded in that day. The blue color shows the payroll tax that the traders pay and it is directly proportional with the market daily volume. The values on the y-axis is in the range of 0 to 7 Billion'

    @output
    @render.text
    def explain_input1():
        return 'Scroll the below bar to see the changes in the graph. The values on the scale denote the minimum number of transactions between two people to be displayed on the heatmap.'
    
    @output
    @render.text
    def explain_graph2():
        return 'The graph above shows the number of transactions and the amount of transaction between two traders. Lighter the colors indicate more number of transactions than darker colors as seen the color scale next to the graph. The white color tells that the transactions between these employees is less than the selected value on the scale. The value that we can see on top of the colors is the transactional amount in USD that has occured between the teo traders. We can clearly see in the graph that, when the nummber of transaction value is 80, there is one combination of traders whose sale value in total is 0 while the number of sales is nearly 200. This can be considered as a clear indication of market manipulation. Although we cannot say the user with actual identification, we can see the wallets that are trying to manipulate and deal with them.'

    @output
    @render.text
    def explain_input2():
        return 'The two sliders below are used to manipulate the tokens that we consider for analysis. All the tokens greater than the mentioned slided value will be considered separatelt and the remaining tokens will be classified as OTHERS'

    @output
    @render.text
    def explain_graph3():
        return 'From the above graph we can see that the input tokens USD Coin, Tether USD, and ETH are the ones that are most used to buy other tokens. While, Curve.fi DAI/USDC/USDT is the most bought output token. The main thing to look over here is that, although ETH and Frax are two of the 5 highly traded tokens, both of them are not used for trading with the highest bought output token and FRAX is used just to buy Curve.fi FRAX/USDC.'

    @output
    @render.text
    def explain_input3():
        return 'Move the slider to consider the tokens that have been swapped greater than the slider value'

    @output
    @render.text
    def explain_graph4():
        return 'From the correlation graph we can see that the token Wrapped Ether is swapped with Tether USD the most. We can say this because, the lighter colors indicate more number of swaps than the darker color. The white color tells us that the swap between teh two currencies is less than the slider value. The values that are annotated on top of the colors indicate the average change in price once the swap is done. For a minimum swap count of 80, we can say that majority of the swaps are successful as only one average value is negative.'
        
    @output
    @render.plot
    def plot():
        data_df = pd.DataFrame(deposits_df[['from', 'to']].value_counts()[deposits_df[['from', 'to']].value_counts() > input.n()]).reset_index()
        amount = pd.DataFrame(deposits_df.groupby(['from', 'to']).agg(sum)[deposits_df[['from', 'to']].value_counts() > input.n()]).reset_index()[['from', 'to', 'amountUSD']]
        data_df.columns = ['trader_a', 'trader_b', 'value']
        amount.columns = ['trader_a', 'trader_b', 'value']
        pivot_table = data_df.pivot(index='trader_a', columns='trader_b', values='value')
        amount = amount.pivot(index='trader_a', columns='trader_b', values='value')
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_title('Amount in USD of transactions for transactions greater than ' + str(input.n()))
        return sns.heatmap(pivot_table, 
                    annot = amount)

    @output
    @render.plot
    def bar_graph():
        output_name = deposits_df.output_name.value_counts()[deposits_df.output_name.value_counts() > input.op()].index
        deposits_df.output_name = deposits_df.output_name.apply(lambda row: 'Other' if row not in output_name else row)
        deposits_df_explode = deposits_df.explode(column = ['input_last_priceUSD', 'input_name'])
        input_name = deposits_df_explode.input_name.value_counts()[deposits_df_explode.input_name.value_counts() > input.ip()]
        deposits_df_explode.input_name = deposits_df_explode.input_name.apply(lambda row: 'Other' if row not in input_name else row)
        return sns.histplot(data = deposits_df_explode, x = "input_name", hue = 'output_name', multiple = 'stack', color = sns.color_palette("colorblind"))

    @output
    @render.plot
    def financial():
        financial_data['totalValueLockedUSD'] = financial_data['totalValueLockedUSD'].astype(float)
        financial_data['dailyVolumeUSD'] = financial_data['dailyVolumeUSD'].astype(float)
        financial_data['dailyProtocolSideRevenueUSD'] = financial_data['dailyProtocolSideRevenueUSD'].astype(float)
        plt.figure(figsize = (20, 12))
        frame1 = plt.gca()
        frame1.axes.xaxis.set_ticklabels([])
        plt.title('Previous market trend')
        return plt.stackplot(financial_data.timestamp, financial_data.dailyProtocolSideRevenueUSD * 1000,
                      financial_data.dailyVolumeUSD, 
                      financial_data.totalValueLockedUSD / 10, alpha = 0.5)

    @output
    @render.plot
    def swapping():
        data_df = swap[['toekn_in_name', 'toekn_out_name']].value_counts().reset_index()
        data_df.columns = ['toekn_in_name', 'toekn_out_name', 'value']
        data_df = data_df[data_df.value > input.swap()]
        fill_vals = data_df.merge(swap.groupby(['toekn_in_name', 'toekn_out_name']).agg(np.mean).reset_index(), how = 'inner')
        fill_vals['value'] = fill_vals.amountInUSD - fill_vals.amountOutUSD
        pivot_table = data_df.pivot(index='toekn_in_name', columns='toekn_out_name', values='value')
        fill_vals = fill_vals.pivot(index='toekn_in_name', columns='toekn_out_name', values='value')
        fig, ax = plt.subplots(figsize=(10, 8))
        matrix = np.triu(pivot_table)
        ax.set_title('Tokens preferred for swapping')
        return sns.heatmap(pivot_table, mask = matrix, annot = fill_vals)

app = App(app_ui, server)
