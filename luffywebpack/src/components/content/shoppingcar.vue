<template>
    <div>
      {{msg}}
    </div>
</template>

<script>
    export default {
        name: "shoppingcar",
        data(){
          return{
            msg:''
          }
        },
        methods:{
          getshopping(){
            var that = this;
            this.$axios.request({
              url:"http://127.0.0.1:8008/api/v2/shopping/" ,
              method:'get',

            }).then(function (arg) {
              arg = JSON.parse(arg.data.data);
              that.msg = arg;
              console.log(arg)
            })
          }
        },
      mounted() {
          this.getshopping()
      }
    }
</script>

<style scoped>

</style>
