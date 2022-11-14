import React, { FC } from "react";
import { CustomerType } from "./types/customer-type";
import { Importer, ImporterField } from "react-csv-importer";
import "react-csv-importer/dist/index.css";
import { toast } from "react-toastify";
import { Customer } from "./api/api";
import { useMutation, useQueryClient } from "react-query";

const ImportCsvCustomers: FC = () => {
  const queryClient = useQueryClient();

  //batch create customers
  const importCustomers = useMutation(
    (post: CustomerType[]) => Customer.batchCreate(post),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_totals"]);
        toast.success("Customer created successfully", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  return (
    <div>
      <Importer
        assumeNoHeaders={false} // optional, keeps "data has headers" checkbox off by default
        restartable={false} // optional, lets user choose to upload another file when import is complete
        onStart={({ file, preview, fields, columnFields }) => {
          // optional, invoked when user has mapped columns and started import
          // prepMyAppForIncomingData();
        }}
        processChunk={async (rows, { startIndex }) => {
          // required, may be called several times
          // receives a list of parsed objects based on defined fields and user column mapping;
          // (if this callback returns a promise, the widget will wait for it before parsing more data)
          const batchCustomers: CustomerType[] = [];
          for (var row of rows) {
            batchCustomers.push({
              customer_id: row.customer_id,
              customer_name: row.customer_name,
              email: row.email,
              payment_provider: row.payment_provider,
              payment_provider_id: row.payment_provider_id,
            });
          }
          importCustomers.mutate(batchCustomers);
        }}
        onComplete={({ file, preview, fields, columnFields }) => {
          // optional, invoked right after import is done (but user did not dismiss/reset the widget yet)
          toast.success("Import complete", {
            position: toast.POSITION.TOP_CENTER,
          });
        }}
        onClose={({ file, preview, fields, columnFields }) => {
          // optional, if this is specified the user will see a "Finish" button after import is done,
          // which will call this when clicked
          // onCancelImport();
        }}

        // CSV options passed directly to PapaParse if specified:
        // delimiter={...}
        // newline={...}
        // quoteChar={...}
        // escapeChar={...}
        // comments={...}
        // skipEmptyLines={...}
        // delimitersToGuess={...}
        // chunkSize={...} // defaults to 10000
        // encoding={...} // defaults to utf-8, see FileReader API
      >
        <ImporterField name="customer_id" label="customer_id" />
        <ImporterField name="email" label="email" />
        <ImporterField name="stripe_id" label="stripe_id" optional />
      </Importer>
    </div>
  );
};

export default ImportCsvCustomers;
