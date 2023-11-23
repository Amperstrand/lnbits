new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      isSuperUser: false,
      wallet: {},
      cancel: {},
      users: [],
      wallets: [],
      walletDialog: {
        title: 'Wallets',
        show: false
      },
      topupDialog: {
        show: false
      },
      walletTable: {
        columns: [
          {
            name: 'name',
            align: 'left',
            label: 'Name',
            field: 'name'
          },
          {
            name: 'currency',
            align: 'left',
            label: 'Currency',
            field: 'currency'
          },
          {
            name: 'balance_msat',
            align: 'left',
            label: 'Balance msat',
            field: 'balance_msat'
          },
          {
            name: 'deleted',
            align: 'left',
            label: 'Deleted',
            field: 'deleted'
          }
        ]
      },
      usersTable: {
        columns: [
          {
            name: 'username',
            align: 'left',
            label: 'Username',
            field: 'username',
            sortable: true
          },
          {
            name: 'email',
            align: 'left',
            label: 'Email',
            field: 'email',
            sortable: true
          },
          {
            name: 'balance_msat',
            align: 'left',
            label: 'Balance msat',
            field: 'balance_msat',
            sortable: true
          },
          {
            name: 'wallet_count',
            align: 'left',
            label: 'Wallet Count',
            field: 'wallet_count',
            sortable: true
          },
          {
            name: 'transaction_count',
            align: 'left',
            label: 'Transaction Count',
            field: 'transaction_count',
            sortable: true
          },
          {
            name: 'transaction_out',
            align: 'left',
            label: 'Outgoing',
            field: 'transaction_out',
            sortable: true
          },
          {
            name: 'transaction_in',
            align: 'left',
            label: 'Incoming',
            field: 'transaction_in',
            sortable: true
          }
        ],
        pagination: {
          sortBy: 'balance_msat',
          rowsPerPage: 10,
          page: 1,
          descending: true,
          rowsNumber: 10
        },
        filter: null,
        loading: false
      }
    }
  },
  created() {
    this.fetchUsers()
  },
  mounted() {
    this.chart1 = new Chart(this.$refs.chart1.getContext('2d'), {
      type: 'bubble',
      options: {
        layout: {
          padding: 20
        }
      },
      data: {
        datasets: [
          {
            label: 'Balance - TX Count (TX Count / 10) million sats',
            backgroundColor: 'rgb(255, 99, 132)',
            data: []
          }
        ]
      }
    })
    this.chart2 = new Chart(this.$refs.chart2.getContext('2d'), {
      type: 'bubble',
      options: {
        layout: {
          padding: 20
        }
      },
      data: {
        datasets: [
          {
            label: 'IN - OUT (TX Count / 10) million sats',
            backgroundColor: 'rgb(0, 99, 132)',
            data: []
          }
        ]
      }
    })
    this.chart3 = new Chart(this.$refs.chart3.getContext('2d'), {
      type: 'pie',
      options: {
        layout: {
          padding: 42
        }
      },
      data: {
        datasets: [
          {
            label: 'Balances',
            data: []
          }
        ],
        labels: []
      }
    })
  },
  methods: {
    usersTableRowKey: function (row) {
      return row.id
    },
    loginAsUser(user) {
      window.open('/wallet?usr=' + user, '_blank')
    },
    loginAsUserWallet(user, wallet) {
      window.open('/wallet?usr=' + user + '&wal=' + wallet, '_blank')
    },
    refreshUsers() {
      this.fetchUsers()
    },
    deleteUser(user_id) {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this user?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/users/api/v1/user/' + user_id + '/?usr=' + this.g.user.id
            )
            .then(() => {
              this.fetchUsers()
              this.$q.notify({
                type: 'positive',
                message: 'Success! User deleted!',
                icon: null
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    undeleteUserWallet(user_id, wallet) {
      LNbits.api
        .request(
          'GET',
          '/users/api/v1/user/' +
            user_id +
            '/wallet/' +
            wallet +
            '/undelete?usr=' +
            this.g.user.id
        )
        .then(() => {
          this.fetchWallets(user_id)
          this.$q.notify({
            type: 'positive',
            message: 'Success! Undeleted user wallet!',
            icon: null
          })
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteUserWallet(user_id, wallet, deleted) {
      const dialogText = deleted
        ? 'Wallet is already deleted, are you sure you want to permanently delete this user wallet?'
        : 'Are you sure you want to delete this user wallet?'
      LNbits.utils.confirmDialog(dialogText).onOk(() => {
        LNbits.api
          .request(
            'DELETE',
            '/users/api/v1/user/' +
              user_id +
              '/wallet/' +
              wallet +
              '/?usr=' +
              this.g.user.id
          )
          .then(() => {
            this.fetchWallets(user_id)
            this.$q.notify({
              type: 'positive',
              message: 'Success! User wallet deleted!',
              icon: null
            })
          })
          .catch(function (error) {
            LNbits.utils.notifyApiError(error)
          })
      })
    },
    updateChart(users) {
      const filtered = users.filter(user => {
        if (
          user.balance_msat === null ||
          user.balance_msat === 0 ||
          user.wallet_count === 0
        ) {
          return false
        }
        return true
      })

      const data = filtered.map(user => {
        return {
          x: user.transaction_count,
          y: user.balance_msat / 1000000000,
          r: user.transaction_count / 10
        }
      })
      this.chart1.data.datasets[0].data = data
      this.chart1.update()

      const data2 = filtered.map(user => {
        return {
          x: user.transaction_in / 1000000000,
          y: user.transaction_out / 100000000,
          r: user.transaction_count / 10
        }
      })
      this.chart2.data.datasets[0].data = data2
      this.chart2.update()

      const COLORS = [
        '#4dc9f6',
        '#f67019',
        '#f53794',
        '#537bc4',
        '#acc236',
        '#166a8f',
        '#00a950',
        '#58595b',
        '#8549ba'
      ]
      const data3 = filtered.map(user => user.balance_msat)
      const labels3 = filtered.map(user => user.id.substring(0, 5))
      const colors3 = filtered.map((_, i) => COLORS[i % COLORS.length])
      this.chart3.data.datasets[0].data = data3
      this.chart3.data.datasets[0].backgroundColor = colors3
      this.chart3.data.labels = labels3
      this.chart3.update()
    },
    fetchUsers(props) {
      const params = LNbits.utils.prepareFilterQuery(this.usersTable, props)
      LNbits.api
        .request(
          'GET',
          '/users/api/v1/user/?usr=' + this.g.user.id + '&' + params
        )
        .then(res => {
          this.usersTable.loading = false
          this.usersTable.pagination.rowsNumber = res.data.total
          this.users = res.data.data
          this.updateChart(this.users)
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    fetchWallets(user_id) {
      LNbits.api
        .request(
          'GET',
          '/users/api/v1/user/' + user_id + '/wallet?usr=' + this.g.user.id
        )
        .then(res => {
          this.wallets = res.data
          this.walletDialog.show = this.wallets.length > 0
          if (!this.walletDialog.show) {
            this.fetchUsers()
          }
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    toggleAdmin(user_id) {
      LNbits.api
        .request(
          'GET',
          '/users/api/v1/user/' + user_id + '/admin?usr=' + this.g.user.id
        )
        .then(() => {
          this.fetchUsers()
          this.$q.notify({
            type: 'positive',
            message: 'Success! Toggled admin!',
            icon: null
          })
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    exportUsers() {
      console.log('export users')
    },
    topupCallback(res) {
      this.wallets.forEach(wallet => {
        if (res.wallet_id === wallet.id) {
          wallet.balance_msat += res.value
        }
      })
      this.fetchUsers()
    },
    topupWallet() {
      LNbits.api
        .request(
          'PUT',
          '/users/api/v1/topup/?usr=' + this.g.user.id,
          this.g.user.wallets[0].adminkey,
          this.wallet
        )
        .then(_ => {
          this.$q.notify({
            type: 'positive',
            message:
              'Success! Added ' + this.wallet.amount + ' to ' + this.wallet.id,
            icon: null
          })
          this.wallet = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    }
  }
})
