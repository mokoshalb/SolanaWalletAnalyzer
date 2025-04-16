# Solana Wallet Analyzer

A powerful tool for analyzing Solana wallet performance, calculating PnL, win rates, and holding periods. This tool helps identify profitable trading patterns and successful wallets on the Solana blockchain.

## Features

- Analyze wallet transactions and performance metrics
- Calculate PnL (Profit and Loss)
- Determine win rates and average holding periods
- Filter wallets based on customizable criteria
- Export results to CSV format
- Real-time price data from Birdeye API

## Installation

1. Clone the repository:
```bash
git clone https://github.com/OkoyaUsman/SolanaWalletAnalyzer.git
cd SolanaWalletAnalyzer
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and add your Birdeye API key:
```bash
BIRDEYE_API_KEY=your_api_key_here
```

## Usage

1. Prepare your wallet list:
   - Create a `solana_wallets.csv` file with wallet addresses (one per line)

2. Run the analyzer:
```bash
python bot.py
```

3. Enter the analysis parameters when prompted:
   - Minimum wallet capital
   - Minimum average holding period
   - Minimum total PnL
   - Minimum win rate
   - Timeframe to analyze

4. Results will be saved in a CSV file with timestamp

## Configuration

The following parameters can be customized in the code:
- Minimum wallet capital
- Minimum average holding period
- Minimum total PnL
- Minimum win rate
- Analysis timeframe options (1h, 4h, 1d, 1w, 1m)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For assistance, customization, or further help, contact me on Telegram: [@okoyausman](https://t.me/okoyausman)

## Disclaimer

This tool is for educational and research purposes only. Use at your own risk. The developers are not responsible for any financial losses incurred while using this tool. 
