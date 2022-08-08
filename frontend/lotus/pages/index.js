import Head from 'next/head'
import Image from 'next/image'
import styles from '../styles/Home.module.css'
import { makeStyles } from "@material-ui/core/styles";
import Table from '../components/Table/table';


const useStyles = makeStyles((theme) => ({
  example: {
    color: 'purple',
  },
}));

export default function Home() {

  const classes = useStyles();

  return (
    <>
    <div className={classes.example}>
      Lotus App
    </div>
    <Table
    tableHeaderColor="warning"
                tableHead={["customer_id", "name", "total_due", "payment_provider_id", "billing_end_date"]}
                tableData={[
                  ["1", "Dakota Rice", "$36,738", "Niger", "10/12/2022"],
                  ["2", "Minerva Hooper", "$23,789", "Curaçao", "10/12/2022"],
                  ["3", "Sage Rodriguez", "$56,142", "Netherlands", "10/12/2022"],
                  ["4", "Philip Chaney", "$38,735", "Korea, South", "10/12/2022"],
                ]} />
    </>
  )
}
