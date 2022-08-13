import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/CustomerTable";
import axios from "axios";

const customer_data = [
  {
    customer_id: "1",
    name: "Leanne Graham",
    plans: 3,
  },
  {
    customer_id: "2",
    name: "Ervin Howell",
    plans: 2,
  },
  { customer_id: "3", name: "Clementine Bauch", plans: 3 },
  { customer_id: "4", name: "Patricia Lebsack", plans: 2 },
];

const ViewCustomers: FC = () => {
  const [data, setData] = useState(customer_data);

  useEffect(() => {
    axios.get(`/api/customers`).then((res) => {
      setData(res.data);
    });
  }, []);

  return (
    <div>
      <CustomerTable customerArray={data} />
    </div>
  );
};

export default ViewCustomers;
