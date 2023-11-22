new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      isSuperUser: false,
      wallet: {},
      cancel: {},
      users: [],
      usersTable: {
        columns: [
          {
            name: 'Usr ID',
            align: 'left',
            label: 'Usr',
            field: 'usr',
            sortable: true
          }
        ],
        pagination: {
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
  computed: {
    endpoint() {
      return '/users/api/v1/user/?usr=' + this.g.user.id
    }
  },
  methods: {
    usersTableRowKey: function (row) {
      return row.usr
    },
    fetchUsers() {
      console.log('fetch users')
      LNbits.api
        .request('GET', this.endpoint)
        .then(res => {
          this.users = res.data
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    exportUsers() {
      console.log('export users')
    },
    deleteUser() {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this user?')
        .onOk(() => {
          LNbits.api
            .request('DELETE', this.endpoint)
            .then(() => {
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
    }
  }
})
