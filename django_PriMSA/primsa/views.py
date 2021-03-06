
#part of django framework to render a template or an HttpResponse
from django.shortcuts import render, HttpResponse

from Bio import Entrez, SeqIO, AlignIO, Phylo
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.Alphabet import IUPAC
from Bio.Alphabet import generic_rna
from Bio.Align import MultipleSeqAlignment

#Connects to clustalw and runs on the commandline
from Bio.Align.Applications import ClustalwCommandline

#To plot graphs
import matplotlib.pyplot as plt

#for creating images with text
from PIL import Image, ImageDraw, ImageFont

import collections

import pylab
from primer3 import bindings

#TRANSLATION TABLE stored as Python Dictionary
codon_table = {
    'ATA':'I', 'ATC':'I', 'ATT':'I', 'ATG':'M',
    'ACA':'T', 'ACC':'T', 'ACG':'T', 'ACT':'T',
    'AAC':'N', 'AAT':'N', 'AAA':'K', 'AAG':'K',
    'AGC':'S', 'AGT':'S', 'AGA':'R', 'AGG':'R',
    'CTA':'L', 'CTC':'L', 'CTG':'L', 'CTT':'L',
    'CCA':'P', 'CCC':'P', 'CCG':'P', 'CCT':'P',
    'CAC':'H', 'CAT':'H', 'CAA':'Q', 'CAG':'Q',
    'CGA':'R', 'CGC':'R', 'CGG':'R', 'CGT':'R',
    'GTA':'V', 'GTC':'V', 'GTG':'V', 'GTT':'V',
    'GCA':'A', 'GCC':'A', 'GCG':'A', 'GCT':'A',
    'GAC':'D', 'GAT':'D', 'GAA':'E', 'GAG':'E',
    'GGA':'G', 'GGC':'G', 'GGG':'G', 'GGT':'G',
    'TCA':'S', 'TCC':'S', 'TCG':'S', 'TCT':'S',
    'TTC':'F', 'TTT':'F', 'TTA':'L', 'TTG':'L',
    'TAC':'Y', 'TAT':'Y', 'TAA':'*', 'TAG':'*',
    'TGC':'C', 'TGT':'C', 'TGA':'*', 'TGG':'W',
}


'''
Scoring Function that returns a PENALTY SCORE
##IDEA: Return higher scores for lower conservation as CONFIDENCE SCORE is INVERSELY proportional to SUM Returned
###
Base case: 3rd position does not matter meaning codes for same aa: Score is given as 1
            3rd position leads to 2 different aa: Base score as (1 + 1)= 2 with addition penalty for each aa:: [same groups: 0.25, similar chemical:0.5, different: 1]
            If stop codon, penalty of 3 is added
###
1. Lowest penalty is received when the base at the third position does not matter
TT: F, L (Both Hydrophobic):: 2 + 0.25 + 0.25 = 2.50 (0.25  penalty, same chemical)
TC: S  :: 1
TA: Y, Stop (2) ::  (1+1 + 1 + 3)= 6 Stop codon is [3] times the penalty and Y is drastically different so plus 1
TG: C (Polar), W (Hydrophobic), Stop(1) :: (1 + 1) + (1 + 1) + (1+ 3) = 8 [1 penalty added to each aa due to the differences and 3 for being a stop codon]
CT: L :: 1
CC: P :: 1
CA: H (Electrically Charged), Q (Polar) :: (1 + 0.5) + (1 + 0.5) = 3 [0.5 penalty is added to each aa as they both have charge and are not drastically different]
CG: R :: 1
AT: I (Hydrophobic), M (Polar) :: (1 + 1) + (1 + 1)= 4
AC: T :: 1
AA: N (Polar), K (Electrically Charged Basic) :: 1 + 0.5 + 1 + 0.5 = 3
AG: S(Polar), R(Electrically Charged) :: 1 + 0.5 + 1 + 0.5 = 3
GT: V :: 1
GC: A :: 1
GA: D (Electrically Charged), E (Electrically Charged) :: 1+0.25 + 1 + 0.25= 2.5
GG: G :: 1
'''

#penalty score for conservation in the third position
codon_table_12={
'TT':2.50, 'TC':1,'TA': 6,'TG':8, 'CT': 1, 'CC': 1, 'CA':3,'CG': 1, 'AT': 4, 'AC': 1, 'AA': 3, 'AG': 3, 'GT': 1,
'GC':1, 'GA': 2.5, 'GG': 1
}



#penalty score for conservation in the second position
codon_table_13={
'TT':6, 'TC':6,'TA': 11,'TG':9, 'CT': 5, 'CC': 5, 'CA':5.25,'CG': 5, 'AT': 6, 'AC': 6, 'AA': 6, 'AG': 5.50, 'GT': 6.50,
'GC':6.50, 'GA': 6.50, 'GG': 6.50
}



#penalty score for conservation in the first position
codon_table_23={
'TT':6, 'TC':6,'TA': 3.75,'TG':4, 'CT': 6.5, 'CC': 6.5, 'CA':6.5,'CG': 6.5, 'AT': 6.5, 'AC': 6.5, 'AA': 8, 'AG': 8, 'GT': 6.50,
'GC':6.50, 'GA': 8, 'GG': 5.0
}

#the dictionary maps the sequence id to its description for phylogenetic trees
tree_map={}

#ACCESSORIES FUNCTIONS to support the views

#RETURNS a total penalty for the lack of conservation based on the position of the conservation
def sum_conservation(l_conservation, consensus_seq):

    index_score={}

    for index in l_conservation:
        position= (index+ 1) %3
        #if the conservation is lower than 50% in the THIRD position
        if position==0:
            #captures the two sequences before the index
            triplet_12= consensus_seq[index-2:index]

            if triplet_12 in codon_table_12.keys():
                index_score[index]=codon_table_12[triplet_12]
            else:
                index_score[index]=10

        #if the conservation is lower than 50% in the FIRST position
        if position==1:
            triplet_23= consensus_seq[index+1:index+3]


            if triplet_23 in codon_table_23.keys():
                index_score[index]=codon_table_23[triplet_23]
            else:
                index_score[index]=10


        #if the conservation is lower than 50% in the SECOND position
        if position==2:
            triplet_13= consensus_seq[index-1] + consensus_seq[index+1]

            if triplet_13 in codon_table_13.keys():
                index_score[index]=codon_table_13[triplet_13]
            else:
                index_score[index]=10


    return sum(index_score.values())

#returns a tuple with counts in the order (A, T, C, G,-)
def countIndBase(col):
    count = {'A' : 0, 'T' : 0, 'C' : 0, 'G' : 0, '-':0}

    for base in col:
        count[base] += 1

    return (count['A'], count['T'], count['C'], count['G'], count['-'])


'''
##########################################################################################
1. Takes a triplet codon list and returns the LONGEST translated protein sequence as string
2. Any protein sequence without the ending stop codon is REJECTED
##########################################################################################
For Instance:
INPUT: *AKSTMNK*SATFRAEGHGSAFTEGST
OUTPUT: AKSTMNK
##########################################################################################
'''

def translation(triplet_list):

    #stores the complete translated polypeptide sequence
    translated_seq=""

    #global counter to keep track of which triplet codon we are on
    global_count=0

    #loops through each triplet codon in the triplet codon list and translates it using the codon table
    for codon in triplet_list:
        translated_seq=translated_seq + codon_table[codon]

    ##STORES THE INFORMATION ABOUT THE LONGEST PEPTIDE AND ITS CORRESPONDING mRNA
    #keeps track of the length of the longest peptide
    longest_peptide_length=0
    #stores the longest peptide seen as of now
    longest_peptide=""
    #stores the corresponding mRNA triplet list
    longest_mRNA=""



    #STORES THE INFORMATION ABOUT THE CURRENT PEPTIDE
    current_peptide_length = 0
    current_peptide_seq=""
    current_mRNA=""
    current_count=0

    #Goes through the translated sequence to find the longest peptide wiith a stop codon
    for aa in translated_seq:

        '''
        LOGIC DESCRIPTION:
        if stop codon is encountered, checks to see if the current polypeptide is the longest
        if YES, replaces the longest as the current else moves on to the next amino acid residues. RESETS the temp counter variables to 0,"" to start a fresh count
        if stop codon is NOT encountered, moves to the next amino acid residue, adds the current to the polypeptide and increases it's length
        '''
        if aa=='*':
            if longest_peptide_length < current_peptide_length:
                longest_peptide_length=current_peptide_length
                longest_peptide=current_peptide_seq
                longest_mRNA=current_mRNA

                #reset the counter variables
                current_peptide_length=0
                current_peptide_seq=""
                current_mRNA=""
                global_count=global_count+1

            else:
                current_peptide_length=0
                current_peptide_seq=""
                current_mRNA=""
                global_count= global_count + 1
                continue
        else:
            current_peptide_length=current_peptide_length + 1
            current_peptide_seq=current_peptide_seq+aa
            current_mRNA= current_mRNA+triplet_list[global_count]
            global_count=global_count +1

    return [longest_peptide,longest_mRNA]


'''
#Takes in the mRNA sequence in string format and returns the longest polypeptide with a stop codon (protein seq) as well as the corresponding mRNA sequence
'''
def find_orf(seq):
    #change the incoming sequence to an uppercase
    seq=seq.upper()

    #split the mRNA sequences into the triplet codons for all the reading frames

    first_frame=list(seq[0+i:3+i] for i in range(0,len(seq), 3))
    second_frame=list(seq[0+i:3+i] for i in range(1,len(seq), 3))
    third_frame=list(seq[0+i:3+i] for i in range(2,len(seq), 3))
    if len(first_frame[-1])<3:
        del first_frame[-1]
    if len(second_frame[-1])<3:
        del second_frame[-1]
    if len(third_frame[-1])<3:
        del third_frame[-1]

    #longest polypeptide from the each reading frame
    first_translation=translation(first_frame)
    second_translation=translation(second_frame)
    third_translation=translation(third_frame)
    #print "seq", seq

    if len(first_translation[0]) > len(second_translation[0]):
        longest_translation=first_translation
    else:
        longest_translation=second_translation
    if len(longest_translation[0]) <len(third_translation[0]):
        longest_translation=third_translation

    return longest_translation


#Takes FILENAME as INPUT and performs MSA using CLUSTALW through COMMANDLINE
def multipleSeqAlignment(fileName):

    cline=ClustalwCommandline("clustalw", infile=fileName)
    cline()


def node_name(leaf):
    if leaf.name !=None:
        return tree_map[leaf.name]
    else:
        return leaf.name






'''
1. Processes given mRNA sequences in FASTA format
2. Finds ORFs, translates the mRNA and then saves the sequences


'''




def tree_draw_newick():

    #open handle to the mRNA sequence from USER
    handle_open=open("user_ncbi_screened.fasta",'r')

    #write handle to the parse mRNA sequence that is coding sequence
    handle_write_mRNA=open("parsed-mrna.fasta", 'w+')

    #write handle containing the translated Protein sequence
    handle_write_protein=open("parsed-protein.fasta",'w+')

    for seq_record in SeqIO.parse(handle_open,'fasta'):

        #returns the longest polypeptide chain with the corresponding mRNA sequence from all the frames for a given mRNA sequence
        orf=find_orf(str(seq_record.seq))
        protein= SeqRecord(Seq(orf[0], IUPAC.protein), id= seq_record.id, description= seq_record.description + "|protein Seq NOT mRNA")
        mRNA= SeqRecord(Seq(orf[1]), id= seq_record.id, description= seq_record.description)
        SeqIO.write(protein, handle_write_protein, "fasta")
        SeqIO.write(mRNA, handle_write_mRNA, "fasta")


    handle_write_mRNA.close()
    handle_write_protein.close()
    handle_open.close()

    multipleSeqAlignment("parsed-protein.fasta")

    alignment= AlignIO.read("parsed-protein.aln", "clustal")
    handle_protein_alignment=open("parsed_protein_alignment.fasta",'w')
    AlignIO.write(alignment, handle_protein_alignment, "fasta")
    handle_protein_alignment.close()

    #stores the number of rows and columns in the protein multiple sequence alignment
    num_col= alignment.get_alignment_length()
    num_row=len(alignment)

    #keeps track of which row
    counter_row=0

    #stores the seqrecord classes of the overlapped sequences
    msa_seq=[]

    #handle to the mRNA sequence corresponding to the protein sequence
    handle_open_mRNA= open("parsed-mrna.fasta", "r")
    #stores the parsed FASTA sequences as a python dictionary
    seq_records =SeqIO.to_dict(SeqIO.parse(handle_open_mRNA, 'fasta'))
    handle_open_mRNA.close()


    #Iterates through all the rows in the alignment specific to a sequence
    while counter_row < num_row:
        #print alignment[counter_row].id
        rna_string=str(seq_records[alignment[counter_row].id].seq)
        rna_id = str(seq_records[alignment[counter_row].id].id)
        rna_description= str(seq_records[alignment[counter_row].id].description)
        rna_triplet_list= list(rna_string[0+i:3+i] for i in range(0,len(rna_string), 3))
        rna_index=0
        counter_column=0
        triplet_align = ""
        while counter_column < num_col:

            #if the value is '-', move to the next column in the row
            #add the '-' to the nucleotide sequence reverse translated to rna

            if alignment[counter_row][counter_column]=='-':
                #I think this is the smartest thing I have done in my life
                triplet_align=triplet_align+'---'
            else:
                triplet_align=triplet_align+rna_triplet_list[rna_index]
                rna_index=rna_index+1
            counter_column=counter_column+1
        msa_seq.append(SeqRecord(Seq(triplet_align), id=rna_id, description=rna_description))
        counter_row=counter_row +1

    #writes the overlapped alignment file
    AlignIO.write(MultipleSeqAlignment(msa_seq), "overlapped_mRNA.fasta", "fasta")


    #Loads the alignment for the overlapped_mRNA
    alignment_overlapped= AlignIO.read("overlapped_mRNA.fasta", "fasta")
    num_col_overlap= alignment_overlapped.get_alignment_length()
    num_row_overlap= len(alignment_overlapped)
    distribution=[]


    consensus_sequence=''


    #stores the collection of tuple with corresponding counts of A,T,C,G,- for each column in the alignment
    tuple_list=[]

    #stores the highest count for each column in the alignment
    max_each_column=[]


    #Stores the value that correspondes to 50%
    half_line= 0.5 * num_row_overlap
    half_line_list= [half_line] * num_col_overlap
    consensus_sequence_5=""

    tuple_to_base=['A','T','C','G','-']

    #Goes through each index in the overlapped alignment
    for index in range(num_col_overlap):
        column_index= alignment_overlapped[:,index]
        count_tuple=countIndBase(column_index)
        tuple_list.append(count_tuple)
        highest_frequency= max(count_tuple)
        index_highest_freq= count_tuple.index(highest_frequency)

        #if - appears the highest number of times, replace it with N
        #creates the consensus sequence
        if index_highest_freq==4:
            consensus_sequence=consensus_sequence + 'N'
        else:
             consensus_sequence=consensus_sequence + tuple_to_base[index_highest_freq]


        #To understand the behavior of the consensus sequence as the constraints are placed..

        #When constraints is 50%; the highest number of times any nucleotide appears must be greater than half
        if highest_frequency >=half_line:
            if index_highest_freq==4:
                consensus_sequence_5=consensus_sequence_5 + 'N'
            else:
                 consensus_sequence_5=consensus_sequence_5 + tuple_to_base[index_highest_freq]
        else:
            consensus_sequence_5=consensus_sequence_5 + 'X'

        #stores the highest frequency at column position in the alignment
        max_each_column.append(highest_frequency)

    #creates a list with indices where the base is conserved in less than 50% of the sequences
    indices_X_5=[pos for pos, char in enumerate(consensus_sequence_5) if char == 'X']
    codon_X_5= [(e+1)%3 for e in indices_X_5 ]
    #gets frequence of each element as a dictionary. 0: third position, 1: first position, 2: second position
    counter=collections.Counter(codon_X_5)
    confidence_score_5=(len(indices_X_5)/sum_conservation(indices_X_5,consensus_sequence)) + (len(consensus_sequence_5)/len(indices_X_5)) +(0.5/len(indices_X_5))


    '''
    Plot the frequence Vs triplet location GRAPH
    '''
    plt.subplot(1,1,1)
    x_labels= [x+1 for x in counter.keys()]
    plt.bar(list(reversed(range(len(counter)))), counter.values(), width=0.5,align='center', alpha=0.5)
    plt.xticks(range(len(counter)), x_labels)
    plt.ylabel("Frequency")
    plt.xlabel("Position in the Triplet where conservation is less than 50%")
    plt.suptitle("Frequency Vs Position in the Triplet where conservation is less than 50% ")
    plt.savefig("/home/savill88/Desktop/senior-project/PriMSA/django_PriMSA/primsa/static/images/frequency.png", bbox_inches='tight', dpi=250 )




    '''
    GRAPH PLOTTING THE FREQUENCIES OF THE BASES AT EACH COLUMN IN THE ALIGNMENT
    '''
    x_val=range(1,num_col_overlap+1)

    #0: A, 1: T, 2: C, 3: G, 4: -
    y_A= [x[0] for x in tuple_list]
    y_T= [x[1] for x in tuple_list]
    y_C=[x[2] for x in tuple_list]
    y_G=[x[3] for x in tuple_list]
    y_dash= [x[4] for x in tuple_list]

    plt.figure(figsize=(15,15))

    plt.suptitle("Graph showing the distribution of the bases in the Multiple Sequence Alignment", fontsize=25)
    plt.subplot(6,1,1)

    plt.plot(x_val, y_A,'r')
    plt.ylabel("As")

    plt.subplot(6,1,2)
    plt.plot(x_val, y_T,'b')
    plt.ylabel("Ts")

    plt.subplot(6,1,3)
    plt.plot(x_val, y_C,'g')
    plt.ylabel(" Cs")

    plt.subplot(6,1,4)
    plt.plot(x_val, y_G,'y')
    plt.ylabel("Gs")

    plt.subplot(6,1,5)
    plt.plot(x_val, y_dash,'m')
    plt.ylabel("- (Dash) Count ")


    plt.subplot(6,1,6)
    plt.plot(x_val, max_each_column,'k', label='_nolegend_')
    plt.plot( x_val, half_line_list, 'c', label='Frequency at 50% conservation')
    plt.ylabel("Highest Frequency")
    plt.xlabel("Alignment Location (Column Number)")
    plt.legend(loc="upper right")

    plt.savefig("/home/savill88/Desktop/senior-project/PriMSA/django_PriMSA/primsa/static/images/statistics.png", bbox_inches='tight', dpi=150 )


    #PRIMER3
    seq_args={'SEQUENCE_ID':'CONSENSUS_SEQ', 'SEQUENCE_TEMPLATE': consensus_sequence}
    global_args= {'PRIMER_OPT_SIZE': 20,'PRIMER_PICK_INTERNAL_OLIGO': 1,'PRIMER_PRODUCT_SIZE_RANGE': [[175,200],[200,225]], 'PRIMER_NUM_RETURN':1}


    results=bindings.designPrimers(seq_args, global_args)


    parsed_results={}
    left_primer=[results['PRIMER_LEFT_0_SEQUENCE'],round(results['PRIMER_LEFT_0_TM'],2),round(results['PRIMER_LEFT_0_GC_PERCENT'],2), round(results['PRIMER_LEFT_0_END_STABILITY'],2), results['PRIMER_LEFT_0'] ]
    right_primer=[results['PRIMER_RIGHT_0_SEQUENCE'],round(results['PRIMER_RIGHT_0_TM'],2),round(results['PRIMER_RIGHT_0_GC_PERCENT'],2), round(results['PRIMER_RIGHT_0_END_STABILITY'],2), results['PRIMER_RIGHT_0']]
    pair_primer=results['PRIMER_PAIR_0_PRODUCT_SIZE']

    parsed_results['Left']= left_primer
    parsed_results['Right']= right_primer
    parsed_results['product_size']= int(pair_primer)
    parsed_results['confidence_score']= round(confidence_score_5,2)
    parsed_results['total_X']= len(indices_X_5)
    parsed_results['total_alignment']= num_col_overlap

    primer_left_index=[results['PRIMER_LEFT_0']]
    primer_right_index=[results['PRIMER_RIGHT_0']]





    #Draws the phylogenetic tree
    treeNewick= Phylo.read("parsed-protein.dnd", "newick")
    #Phylo.draw_ascii(treeNewick)
    treeNewick.rooted=True
    #note sure what this does
    treeNewick.ladderize()
    Phylo.draw(treeNewick, do_show=False, label_func= node_name)
    pylab.axis('on')
    pylab.savefig("/home/savill88/Desktop/senior-project/PriMSA/django_PriMSA/primsa/static/images/phylotree.png", dpi=300)

    #draw the primer alignment as output
    primer_right_start_index= primer_right_index[0][0] -primer_right_index[0][1] + 1
    primer_right_end_index= primer_right_index[0][0] + 1
    primer_left_start_index=primer_left_index[0][0]
    primer_left_end_index=primer_left_start_index+primer_left_index[0][1]

    primer_left_space=" "* ((primer_left_start_index%100)+2)
    #print primer_left_space
    if (primer_left_end_index% 100) < primer_left_index[0][1]:
        primer_left_line= primer_left_space + '>' * (primer_left_index[0][1] - (primer_left_end_index%100))+"\n\n"
    else:
        primer_left_line= primer_left_space + '>' * primer_left_index[0][1] +"\n\n"

    primer_right_space= " " * ((primer_right_start_index%100) + 2)


    if (primer_right_end_index% 100) < primer_right_index[0][1]:
        primer_right_line= primer_right_space + '<' * (primer_right_index[0][1] - (primer_right_end_index%100))+"\n\n"
    else:
        primer_right_line= primer_right_space + '<' * primer_right_index[0][1] +"\n\n"



    with_new_line="\n"

    count = 1
    for index in range(0,len(consensus_sequence),100):
        with_new_line=with_new_line+"  "+consensus_sequence[index: index+100] + " " +str(count) +'\n'
        if (primer_left_start_index - index)>0 and  (primer_left_start_index - index)<100:

            with_new_line = with_new_line + primer_left_line

        if (primer_right_start_index - index)>0 and (primer_right_start_index-index) <100:

            with_new_line = with_new_line + primer_right_line

        count=count + 100




    font = ImageFont.truetype("FreeMono.ttf", 16, encoding="unic")

    img = Image.new('RGB', (1300, 600), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.multiline_text((0,0), with_new_line, font=font,spacing=20,fill=(0, 0, 0))


    img.save('/home/savill88/Desktop/senior-project/PriMSA/django_PriMSA/primsa/static/images/primer.png')



    return parsed_results





#END of ACCESSORIES FUNCTIONS




# Create your views here.

#renders the INTRODUCTION page
def intro(request):
    return render(request, 'primsa/intro.html')

#renders the INPUT page
def index(request):
    return render(request, 'primsa/index.html')

#renders the summary of the results from the user's query on Entrez database
def ncbi(request):
    results_esearch={}
    if request.method == 'POST':
        try:
            user_email = request.POST.get('userEmail')
            gene_name= request.POST.get('geneName')
            org_genus= request.POST.get('orgGenus')
            org_kingdom= request.POST.get('orgKingdom')

            #creates a search term based on user's inputs
            search_term= gene_name+'[GENE]' + ' AND ' + org_kingdom+'[filter]' +' AND ' + 'biomol_mrna[PROP]' + ' OR ' + org_genus +'[ALL FIELDS]' + " AND refseq[filter]"

            #Entrez preparation
            Entrez.email=user_email

            #access Nucleotide database using Entrez's esearch method, allows for use of History feature
            handle_esearch=Entrez.esearch('nuccore',search_term, useHistory=True)
            esearch_records=Entrez.read(handle_esearch)

            #parses the esearch_records for Output
            for key, value in esearch_records.items():
                if key == 'Count':
                    results_esearch[key]= value
                elif key=='QueryTranslation':
                    results_esearch[key]=value
                elif key=='WebEnv':
                    results_esearch[key]=value
                elif key=='QueryKey':
                    results_esearch[key]=value

            return render(request, 'primsa/summary_esearch.html', {'data': results_esearch})
        except:
            return HttpResponse ('Something went wrong. Please go back and try again.')

#downloads the sequences from NCBI using Entrez Utils webenv and history features
#allows the user to select the sequences for MSA, and Primer Design
def download(request):
    seq_inf={}
    if request.method=='POST':
        count= request.POST.get('Count')
        count = int(count)
        web_env= request.POST.get('WebEnv')
        query_key= request.POST.get('QueryKey')
        batch_size= 50

        handle_write=open("user_ncbi.fasta",'w')

        #code copied from Biopython tutorial pdf
        for start in range(0, count, batch_size):
                   end=min(count, start+batch_size)
                   #print("Going to download record %i to %i" % (start+1, end))
                   fetch_handle= Entrez.efetch(db='nuccore', rettype="fasta", retstart=start, retmax= batch_size, webenv=web_env, query_key=query_key)
                   data=fetch_handle.read()# can't use Entrez.read(fetch_handle) because the file is not in XML
                   fetch_handle.close()
                   handle_write.write(data)
        handle_write.close()

        handle_open=open("user_ncbi.fasta", 'r')

        for seq_record in SeqIO.parse(handle_open,'fasta'):
            temp=[]
            temp.append(seq_record.seq[0:20])
            temp.append(len(seq_record.seq))
            temp.append( seq_record.description)
            seq_inf[seq_record.id]= temp
        handle_open.close()

        return render(request, 'primsa/retrieve.html', {'data': seq_inf})





#this works: tested April 6th, 2017
def clustal(request):
    #sequence IDs selected by user for MSA
    selected_ids=[]

    #Further screening to remove sequences with size 0 or any genome sequences
    filtered_ids=[]


    #the POST request contains the ids for the selected sequences
    if request.method=='POST':
        for key in request.POST:
            if key!='csrfmiddlewaretoken':
                selected_ids.append(key)

    #FILE HANDLES for reading and writing files
    handle_open= open('user_ncbi.fasta','r')
    handle_write=open('user_ncbi_screened.fasta','w')

    for seq_record in SeqIO.parse(handle_open,'fasta'):
        #CONSTRAINTS: Sequence Length >0, Sequence NOT Genomic, Sequence SELECTED by the USER
        if (len(seq_record.seq) != 0) and not ('genome' in seq_record.description) and (seq_record.id in selected_ids):
            #CREATES a NEW Fasta file with only the sequences matching the
            #CONSTRAINTS mentioned above
            SeqIO.write(seq_record, handle_write,"fasta")
            filtered_ids.append(seq_record.id)
            split_string= seq_record.description.split()
            first_four= " ".join(split_string[0:4])
            tree_map[seq_record.id]= first_four

    handle_write.close()
    handle_open.close()


    results=tree_draw_newick()

    return render(request,'primsa/results.html', {'data':results})

    #testing for changing the node label
    #return render(request,'primsa/summary_esearch.html', {'data':tree_map})




def msa(request):

    if request.method=='POST':
        write_handle=open("user_ncbi_screened.fasta",'w')
        write_handle.write(request.POST.get('fastaSeqs'))
        write_handle.close()

        handle_open=open("user_ncbi_screened.fasta",'r')
        for seq_record in SeqIO.parse(handle_open,"fasta"):
            split_string= seq_record.description.split()
            first_four= " ".join(split_string[0:4])
            tree_map[seq_record.id]= first_four

        results=tree_draw_newick()

        return render(request,'primsa/results.html', {'data':results})
